import abc
import copy
import shutil
import time
import wave

from .base_getter import BaseDataGetter

from core.lib.common import ClassFactory, ClassType, LOGGER, FileOps, Context, Counter, NameMaintainer
from core.lib.network import http_request
from core.lib.estimation import TimeEstimator

__all__ = ('HttpAudioGetter',)


@ClassFactory.register(ClassType.GEN_GETTER, alias='http_audio')
class HttpAudioGetter(BaseDataGetter, abc.ABC):
    def __init__(self):
        self.file_name = None
        self.hash_codes = None

        self.file_suffix = 'wav'

    @TimeEstimator.estimate_duration_time
    def request_source_data(self, system, task_id):
        response = None
        while not response:
            response = http_request(url=system.audio_data_source, no_decode=True, stream=True)
            self.file_name = NameMaintainer.get_task_data_file_name(system.source_id, task_id, self.file_suffix)

            with open(self.file_name, 'wb') as f:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, f)

    @staticmethod
    def compute_cost_time(system, cost):
        return max(1 / system.meta_data['fps'] - cost, 0)

    def __call__(self, system):
        new_task_id = Counter.get_count('task_id')
        delay = self.request_source_data(system, new_task_id)

        sleep_time = self.compute_cost_time(system, delay)
        LOGGER.info(f'[Audio Simulation] source {system.source_id}: sleep {sleep_time}s')
        time.sleep(sleep_time)

        data_source = wave.open(self.file_name, 'r')
        nchannels, sampwidth, framerate, nframes = data_source.getparams()[:4]

        metadata = copy.deepcopy(system.meta_data).update({'nchannels': nchannels, 'sampwidth': sampwidth,
                                                           'framerate': framerate})

        new_task = system.generate_task(new_task_id, system.task_dag, metadata, self.file_name, self.hash_codes)
        system.submit_task_to_controller(new_task)

        FileOps.remove_file(self.file_name)
