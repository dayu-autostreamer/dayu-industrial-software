from typing import List
import os
import glob
import uvicorn
import uuid
import wave
import argparse
import socket
import requests
import threading
import time
import asyncio
from pydantic import BaseModel

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.routing import APIRouter
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


class AudioSource:
    def __init__(self, data_root, play_mode):
        self.router = APIRouter()
        self.router.add_api_route('/file', self.get_source_file, methods=['GET'])

        self.data_root = data_root
        self.data_dir = self.data_root

        self.play_mode = play_mode
        self.frames_per_task = 1

        self.file_name_prefix = 'temp_audio_data'
        self.file_name_suffix = 'wav'

        self._wav_files = self._scan_wavs()
        self._wav_idx = 0  # Next wav index to load
        self._cur_wav_path = None  # Current wav path
        self._cur_params = None  # wave params: (nchannels, sampwidth, framerate, nframes, comptype, compname)
        self._single_len_frames = None
        self._num_segments: int = 0  # Current number of segments that can be split from the wav file
        self._segment_idx: int = 0  # Current wav's next segment index

        self._lock = threading.Lock()

    def get_one_audio_file(self):
        """
        Take the next segment of the audio, save it as an independent wav file, and return the file path.
        """
        with self._lock:
            if not self._wav_files:
                raise HTTPException(status_code=404, detail="No audio files found in data_dir")

            if not self._ensure_ready():
                # Non-cycle and no more data
                raise HTTPException(status_code=404, detail="No more data to play (non-cycle)")

            # Calculate the starting position and length (frame number) of the current segment.
            nchannels, sampwidth, framerate, nframes = self._cur_params[:4]
            start_frame = self._segment_idx * self._single_len_frames
            cur_nframes = min(self._single_len_frames, nframes - start_frame)
            if cur_nframes <= 0:
                # The file has been exhausted, move to the next file.
                self._segment_idx = self._num_segments
                if not self._ensure_ready():
                    raise HTTPException(status_code=404, detail="No more data to play (non-cycle)")
                # Once by recursion; protected by a lock and the next one will have a valid segment
                return self.get_one_audio_file()

            # Read the segment and write temporary wav
            with wave.open(self._cur_wav_path, 'rb') as src:
                src.setpos(start_frame)
                audio_data = src.readframes(cur_nframes)

            file_name = f'{self.file_name_prefix}_{uuid.uuid4().hex}.{self.file_name_suffix}'

            with wave.open(file_name, 'wb') as dst:
                dst.setparams(self._cur_params)   # 先拷贝原参数
                dst.setnframes(cur_nframes)       # 再指定当前段的帧数
                dst.writeframes(audio_data)

            self._segment_idx += 1  # 下次请求取下一段

            return file_name

    def get_source_file(self, backtask: BackgroundTasks):
        file_name = self.get_one_audio_file()
        return FileResponse(path=file_name, filename=file_name, media_type='application/octet-stream',
                            background=backtask.add_task(FileOps.remove_file, file_name))

    def _scan_wavs(self) -> List[str]:
        files = sorted(
            [p for p in glob.glob(os.path.join(self.data_dir, '*'))
             if p.lower().endswith(('.wav', '.wave'))]
        )
        LOGGER.debug(f"Found {len(files)} wav files in {self.data_dir}")
        return files

    def _ensure_ready(self) -> bool:
        """
        If the current wav is not loaded or the segments for the current wav are exhausted, the next wav is loaded.

        When all wav are used up, press play_mode to process it.
        """
        if self._cur_wav_path is None or self._segment_idx >= self._num_segments:
            return self._load_next_wav()
        return True

    def _load_next_wav(self) -> bool:
        """
        Load the next available wav file and prepare its segment information.
        """
        if not self._wav_files:
            return False

        max_attempts = len(self._wav_files)
        attempts = 0

        while attempts < max_attempts:
            # When all wav files are exhausted, decide whether to loop based on play_mode.
            if self._wav_idx >= len(self._wav_files):
                if self.play_mode == 'cycle':
                    self._wav_idx = 0
                else:
                    return False

            path = self._wav_files[self._wav_idx]
            try:
                with wave.open(path, 'rb') as src:
                    params = src.getparams()
                    nchannels, sampwidth, framerate, nframes = params[:4]

                if framerate <= 0 or nframes <= 0:
                    raise ValueError(f"Invalid audio params: framerate={framerate}, nframes={nframes}")

                # Calculate the frame count per segment and the number of segments (round up).
                single_len_frames = int(max(1, round(self.frames_per_task * framerate)))
                num_segments = (nframes + single_len_frames - 1) // single_len_frames

                # Set the current wav's status
                self._cur_wav_path = path
                self._cur_params = params
                self._single_len_frames = single_len_frames
                self._num_segments = num_segments
                self._segment_idx = 0

                LOGGER.info(f"Loaded audio: {os.path.basename(path)} | "
                            f"{nchannels}ch, {sampwidth * 8}bit, {framerate}Hz, {nframes}frames, "
                            f"chunk={single_len_frames} frames (~{self.frames_per_task:.3f}s), "
                            f"segments={num_segments}")

                # Point to the next file (wait until the next time it needs to be loaded)
                self._wav_idx += 1
                return True

            except Exception as e:
                LOGGER.exception(f"Failed to load audio {path}: {e}")
                # Skip bad files and try the next one
                self._wav_idx += 1
                attempts += 1

        return False


@app.post("/admin/add_source")
async def add_source(request: SourceRequest):
    if request.path in sources:
        return {"status": "error", "message": "Path already exists"}
    source = AudioSource(request.root, request.play_mode)
    app.include_router(source.router, prefix=f"/{request.path}")
    LOGGER.info(f"Added source: {request.path}")
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
