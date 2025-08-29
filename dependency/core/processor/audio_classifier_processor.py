import wave
import copy

from .processor import Processor

from core.lib.estimation import Timer
from core.lib.content import Task
from core.lib.common import Context, convert_ndarray_to_list
from core.lib.common import ClassFactory, ClassType


@ClassFactory.register(ClassType.PROCESSOR, alias='audio_classifier_processor')
class AudioClassifierProcessor(Processor):
    def __init__(self):
        super().__init__()

        self.classifier = Context.get_instance('AudioClassifier')

    def __call__(self, task: Task):
        data_file_path = task.get_file_path()

        with wave.open(data_file_path, 'r') as f:
            content = f.readframes(f.getnframes())

        meta_data = copy.deepcopy(task.get_metadata())

        result = self.infer(content, meta_data)
        task.set_current_content(result)

        return task

    def infer(self, data, meta_data):
        assert self.classifier, 'No audio classifier defined!'

        with Timer(f'Audio Classifier'):
            process_output = self.classifier(data, meta_data)

        return process_output
