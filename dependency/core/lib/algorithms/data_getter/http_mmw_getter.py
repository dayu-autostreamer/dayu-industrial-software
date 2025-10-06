import abc
import copy
import shutil
import time
import wave

from .base_getter import BaseDataGetter

from core.lib.common import ClassFactory, ClassType, LOGGER, FileOps, Context, Counter, NameMaintainer
from core.lib.network import http_request
from core.lib.estimation import TimeEstimator

__all__ = ('HttpMMWaveGetter',)


@ClassFactory.register(ClassType.GEN_GETTER, alias='http_mmwave')
class HttpMMWaveGetter(BaseDataGetter, abc.ABC):
    def __init__(self):
        LOGGER.debug('find mmwave getter!')
        self.file_name = None
        self.hash_codes = None

        self.file_suffix = 'bin'

    # 每一帧都是一个bin

    @TimeEstimator.estimate_duration_time
    def request_source_data(self, system, task_id):
        LOGGER.debug(f'url:{system.mmwave_data_source}')
        response = None
        while not response:
            response = http_request(url=system.mmwave_data_source + '/file', no_decode=True, stream=True)
            LOGGER.debug(response)
            self.file_name = NameMaintainer.get_task_data_file_name(system.source_id, task_id, self.file_suffix)
            if response and response.status_code == 200:
                with open(self.file_name, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:  # 避免写入 keep-alive 空块
                            f.write(chunk)

    @staticmethod
    def compute_cost_time(system, cost):
        # 每次拉取一帧的数据(一帧为一个bin),因此实际时间是1/fps
        return max(1 / system.meta_data['fps'] - cost, 0)

    def __call__(self, system):
        new_task_id = Counter.get_count('task_id')
        delay = self.request_source_data(system, new_task_id)

        sleep_time = self.compute_cost_time(system, delay)
        LOGGER.info(f'[Mmwave Simulation] source {system.source_id}: sleep {sleep_time}s')
        time.sleep(sleep_time)

        # 原始的metadata只有fps.
        #
        # data_source = wave.open(self.file_name, 'r')
        # nchannels, sampwidth, framerate, nframes = data_source.getparams()[:4]
        # 
        # metadata = copy.deepcopy(system.meta_data).update({'nchannels': nchannels, 'sampwidth': sampwidth,
        #                                                    'framerate': framerate})

        new_task = system.generate_task(new_task_id, system.task_dag, system.meta_data, self.file_name, self.hash_codes)
        system.submit_task_to_controller(new_task)

        FileOps.remove_file(self.file_name)
