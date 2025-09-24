import copy
import wave

from .processor import Processor

from core.lib.estimation import Timer
from core.lib.content import Task
from core.lib.common import Context
from core.lib.common import ClassFactory, ClassType


@ClassFactory.register(ClassType.PROCESSOR, alias='audio_sampler_processor')
class AudioSamplerProcessor(Processor):
    def __init__(self):
        super().__init__()

        self.sampler = Context.get_instance('Audio_Sampler')
        self.resample_rate = Context.get_parameter('RESAMPLE_RATE', direct=False)

    def __call__(self, task: Task):
        data_file_path = task.get_file_path()
        with wave.open(data_file_path, 'r') as f:
            audio_params = f.getparams()
            audio_data = f.readframes(f.getnframes())

        meta_data = copy.deepcopy(task.get_metadata())
        meta_data.update({'resample_rate': self.resample_rate})

        result = self.infer(audio_data, meta_data)

        with wave.open(data_file_path, 'w') as f:
            f.setparams(audio_params)
            f.writeframes(result)
        return task

    def infer(self, data, metadata):
        assert self.sampler, 'No audio sampler defined!'

        with Timer(f'Audio Sampler'):
            process_output = self.sampler(data, metadata)

        return process_output
