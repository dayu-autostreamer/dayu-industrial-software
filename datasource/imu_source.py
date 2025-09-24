from typing import List
import os
import glob
import numpy as np
import pandas as pd
import uvicorn
import argparse
import socket
import requests
import threading
import time
import asyncio
from pydantic import BaseModel

from fastapi import FastAPI
from fastapi import APIRouter, BackgroundTasks, HTTPException
from starlette.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from core.lib.common import FileOps, LOGGER

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
sources = {}


class SourceRequest(BaseModel):
    root: str
    path: str
    play_mode: str


class IMUSource:
    def __init__(self, data_root, play_mode):
        self.router = APIRouter()
        self.router.add_api_route('/file', self.get_source_file, methods=['GET'])

        self.data_root = data_root
        self.data_dir = self.data_root

        self.play_mode = play_mode

        self.file_name = 'temp_imu_data.npy'

        self._csv_files = self._scan_csvs()
        self._csv_idx: int = 0  # point to next csv index
        self._cur_csv_df = None
        self._cur_csv_path = None
        self._segments = []  # [(start_idx, end_idx_inclusive), ...]
        self._segment_idx = 0  # next segment index in current csv

        self._cur_id = 0

        self._lock = threading.Lock()

    def get_one_imu_file(self):
        with self._lock:

            if not self._csv_files:
                raise HTTPException(status_code=404, detail="No CSV files found in data_dir")

            # If necessary, load a new CSV (or loop/terminate)
            if not self._ensure_csv_ready():
                # Non-cycle mode and no more data
                raise HTTPException(status_code=404, detail="No more data to play (non-cycle)")

            # The current CSV, if it has no segments, degrades to a single segment of the entire file.
            if len(self._segments) == 0 and self._cur_csv_df is not None:
                self._segments = [(0, len(self._cur_csv_df) - 1)]
                self._segment_idx = 0

            # Fetch the current section
            start_idx, end_idx = self._segments[self._segment_idx]
            assert self._cur_csv_df is not None
            data = self._extract_segment(start_idx, end_idx, self._cur_csv_df)

            self._cur_id += 1
            np.save(self.file_name, data)

            self._segment_idx += 1

    def get_source_file(self, backtask: BackgroundTasks):
        self.get_one_imu_file()
        return FileResponse(path=self.file_name, filename=self.file_name, media_type='text/plain',
                            background=backtask.add_task(FileOps.remove_file, self.file_name))

    def _scan_csvs(self) -> List[str]:
        files = sorted(glob.glob(os.path.join(self.data_dir, '*.csv')))
        LOGGER.info(f"Found {len(files)} csv files in {self.data_dir}")
        return files

    def _ensure_csv_ready(self) -> bool:
        """
        Ensure that the current CSV is in a retrievable segment state:
            - If the CSV has not been loaded or the current CSV segment has been exhausted, load the next CSV
            - If the end of the CSV has been reached: cycle back to the beginning, non-cycle returns False
        """
        # If the current CSV is exhausted (or not yet loaded)
        if self._cur_csv_df is None or self._segment_idx >= len(self._segments):
            # Reached the end of all CSV files
            if self._csv_idx >= len(self._csv_files):
                if self.play_mode == 'cycle':
                    self._csv_idx = 0
                else:
                    return False

            # Load the next CSV (skip potentially corrupted files)
            max_attempts = len(self._csv_files)
            attempts = 0
            while attempts < max_attempts:
                self._cur_csv_path = self._csv_files[self._csv_idx]
                try:
                    df = pd.read_csv(self._cur_csv_path)
                    self._cur_csv_df = df
                    start_ids, end_ids = self._end_point_detection(df)
                    # Normalized to int and closed interval
                    self._segments = [(int(s), int(e)) for s, e in zip(start_ids, end_ids)]
                    self._segment_idx = 0
                    # Point to the next CSV (load when needed next time)
                    self._csv_idx += 1
                    break
                except Exception as e:
                    LOGGER.exception(f"Failed to load/parse CSV {self._cur_csv_path}: {e}")
                    # Skip bad files and keep trying
                    self._csv_idx += 1
                    if self._csv_idx >= len(self._csv_files):
                        if self.play_mode == 'cycle':
                            self._csv_idx = 0
                        else:
                            return False
                    attempts += 1
            else:
                # No available CSV
                return False

        return True

    def _extract_segment(self, start_idx: int, end_idx: int, df: pd.DataFrame) -> np.ndarray:
        """
        Extract [start_idx, end_idx] (closed interval) as a numpy array and perform unit conversion:
            - timestamp: 1st column (slicing 1:2)
            - gyro (angular velocity): 6th to 8th columns (6:9), unit deg/s -> rad/s
            - acc (linear acceleration): 19th to 21st columns (19:22), unit g -> m/s^2 (multiply by 9.81)
        """
        if len(df) == 0:
            raise HTTPException(status_code=400, detail="Empty CSV")

        # Boundary Protection & Converted to Half-Open Interval
        s = max(0, int(start_idx))
        e = min(len(df) - 1, int(end_idx))
        if s > e:
            raise HTTPException(status_code=400, detail=f"Invalid segment range: {s}..{e}")

        # Column Range Check (If your CSV column layout is different, please adjust it accordingly)
        need_max_col = 21  # We used column index 21 (starting from 0).
        if df.shape[1] <= need_max_col:
            raise HTTPException(
                status_code=400,
                detail=f"CSV has only {df.shape[1]} columns, need at least 22 columns for slicing."
            )

        # Slice by column according to the original code
        linear_acceleration = df.iloc[:, 19:22].to_numpy()
        angular_velocity = df.iloc[:, 6:9].to_numpy()
        timestamp = df.iloc[:, 1:2].to_numpy()

        # Unit Conversion
        angular_velocity = angular_velocity / 180.0 * np.pi
        linear_acceleration = linear_acceleration * 9.81

        # Segment Extraction (Note that e is a closed interval, and +1 is needed to convert it to a half-open interval)
        data_time = timestamp[s:e + 1, :]
        data_gyro = angular_velocity[s:e + 1, :]
        data_acc = linear_acceleration[s:e + 1, :]

        data = np.column_stack((data_time, data_gyro, data_acc))
        return np.ascontiguousarray(data)

    def _end_point_detection(self, csv_df):
        import numpy as np

        n = len(csv_df)
        if n == 0:
            return [], []

        t = csv_df.iloc[:, 1].to_numpy(dtype=float)

        gap_threshold = getattr(self, "gap_threshold", 0.5)
        ts_in_ms = getattr(self, "timestamp_in_ms", False)
        min_len = int(getattr(self, "min_len", 1))

        if ts_in_ms:
            t = t / 1000.0

        dt = np.diff(t)
        dt[~np.isfinite(dt)] = 0.0

        cuts = np.where(dt > float(gap_threshold))[0]

        starts = np.r_[0, cuts + 1]
        ends = np.r_[cuts, n - 1]

        if min_len > 1:
            keep = (ends - starts + 1) >= min_len
            starts = starts[keep]
            ends = ends[keep]

        if starts.size == 0:
            starts = np.array([0], dtype=int)
            ends = np.array([n - 1], dtype=int)

        return starts.astype(int).tolist(), ends.astype(int).tolist()


@app.post("/admin/add_source")
async def add_source(request: SourceRequest):
    if request.path in sources:
        return {"status": "error", "message": "Path already exists"}
    source = IMUSource(request.root, request.play_mode)
    app.include_router(source.router, prefix=f"/{request.path}")
    sources[request.path] = source
    return {"status": "success"}


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def wait_for_port(port: int, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.5)
    return False


def run_server(port: int):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


def register_source(root: str, path: str, play_mode: str):
    try:
        response = requests.post(
            f"http://127.0.0.1:{server_port}/admin/add_source",
            json={"root": root, "path": path, "play_mode": play_mode}
        )
        LOGGER.info(f"{path} registered to existing server: {response.json()}")

    except Exception as e:
        LOGGER.warning(f"{path} failed to register: {str(e)}")
        LOGGER.exception(e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=str, required=True)
    parser.add_argument('--address', type=str, required=True)
    parser.add_argument('--play_mode', type=str, required=True)
    args = parser.parse_args()

    server_port = int(args.address.split(':')[-1].split('/')[0])
    server_path = args.address.split('/')[-1]

    if is_port_in_use(server_port):
        # server already in running
        register_source(args.root, server_path, args.play_mode)
    else:
        # first run server
        server_thread = threading.Thread(target=run_server, args=(server_port,), daemon=True)
        server_thread.start()
        if wait_for_port(server_port):
            register_source(args.root, server_path, args.play_mode)
            server_thread.join()
        else:
            LOGGER.warning(f"Failed to start server on port {server_port}")
