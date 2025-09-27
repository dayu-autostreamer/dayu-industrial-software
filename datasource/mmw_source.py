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


class MMWSource:
    def __init__(self, data_root, play_mode):
        self.router = APIRouter()
        self.router.add_api_route('/file', self.get_source_file, methods=['GET']) # 核心在这里,把/file路由整到self.get_source_file方法上

        self.data_root = data_root
        self.data_dir = self.data_root

        self.play_mode = play_mode

        self._bin_files = self._scan_bins()
        self._bin_idx: int = 0

        self._lock = threading.Lock()

    def _scan_bins(self) -> List[str]:
        files = sorted(
            [p for p in glob.glob(os.path.join(self.data_dir, '*'))
             if p.lower().endswith(('.bin'))]
        )
        LOGGER.debug(f"Found {len(files)} bin files in {self.data_dir}")
        return files

    def get_one_mmw_file(self):
        with self._lock:
            if not self._bin_files:
                raise HTTPException(status_code=404, detail="No mmw files found in data_dir")
            if self._bin_idx >= len(self._bin_files):
                if self.play_mode == 'cycle':
                    self._bin_idx = 0
                else:
                    return
        return self._bin_files[self._bin_idx]

    def get_source_file(self, backtask: BackgroundTasks):
        LOGGER.debug('hello!!')
        file_name = self.get_one_mmw_file()
        self._bin_idx += 1
        return FileResponse(path=file_name, filename=file_name, media_type='application/octet-stream')


@app.post("/admin/add_source")
async def add_source(request: SourceRequest):
    if request.path in sources:
        return {"status": "error", "message": "Path already exists"}
    source = MMWSource(request.root, request.play_mode)
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
