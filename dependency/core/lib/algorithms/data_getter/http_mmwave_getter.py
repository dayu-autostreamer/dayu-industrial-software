import abc
import time
import os

from .base_getter import BaseDataGetter

from core.lib.common import ClassFactory, ClassType, LOGGER, FileOps, Counter, NameMaintainer
from core.lib.network import http_request
from core.lib.estimation import TimeEstimator

__all__ = ('HttpMMWaveGetter',)


@ClassFactory.register(ClassType.GEN_GETTER, alias='http_mmwave')
class HttpMMWaveGetter(BaseDataGetter, abc.ABC):
    def __init__(self):
        self.file_name = None
        self.hash_codes = None

        self.file_suffix = 'bin'

    @TimeEstimator.estimate_duration_time
    def request_source_data(self, system, task_id):
        # how many bin frames per task
        buffer_size = max(int(system.meta_data.get('buffer_size', 1)),1)
        LOGGER.debug(f'Current buffer size of mmWave data: {buffer_size}')

        # Download multiple frames and zip them
        tmp_dir = f"mmwave_frames_{system.source_id}_{task_id}"
        FileOps.create_directory(tmp_dir)

        downloaded = 0
        attempts = 0
        max_attempts = buffer_size * 3  # simple retry budget
        while downloaded < buffer_size and attempts < max_attempts:
            attempts += 1
            resp = http_request(url=system.mmwave_data_source + '/file', no_decode=True, stream=True)
            if not resp or resp.status_code != 200:
                continue
            out_path = os.path.join(tmp_dir, f"frame_{downloaded}.bin")
            try:
                with open(out_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                downloaded += 1
            except Exception as e:
                LOGGER.warning(f'Failed to write mmwave frame {downloaded}: {e}')
                if os.path.exists(out_path):
                    FileOps.remove_file(out_path)
                continue

        # Ensure at least one file is downloaded
        if downloaded == 0:
            raise RuntimeError('Failed to download any mmwave frames for zipping')

        # Create zip archive
        zip_name = NameMaintainer.get_task_data_file_name(system.source_id, task_id, 'zip')
        FileOps.zip_directory(dir_path='.', zip_name=zip_name, data_dir=tmp_dir)
        self.file_name = zip_name
        # Clean temp dir
        FileOps.remove_file(tmp_dir)

    @staticmethod
    def compute_cost_time(system, cost):
        # If batching multiple frames per task, total period equals buffer_size/fps
        fps = float(system.meta_data.get('fps', 1))
        buffer_size = int(system.meta_data.get('buffer_size', 1))
        period = max(buffer_size, 1) / max(fps, 1e-6)
        return max(period - cost, 0)

    def __call__(self, system):
        new_task_id = Counter.get_count('task_id')
        delay = self.request_source_data(system, new_task_id)

        sleep_time = self.compute_cost_time(system, delay)
        LOGGER.info(f'[Mmwave Simulation] source {system.source_id}: sleep {sleep_time}s')
        time.sleep(sleep_time)

        new_task = system.generate_task(new_task_id, system.task_dag, system.meta_data, self.file_name, self.hash_codes)
        system.submit_task_to_controller(new_task)

        FileOps.remove_file(self.file_name)
