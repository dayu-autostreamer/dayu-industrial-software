import cv2
import copy

from .processor import Processor

from core.lib.estimation import Timer
from core.lib.content import Task
from core.lib.common import Context, EncodeOps
from core.lib.common import ClassFactory, ClassType


@ClassFactory.register(ClassType.PROCESSOR, alias='universal_processor')
class UniversalProcessor(Processor):
    def __init__(self):
        super().__init__()

        self.processor = Context.get_instance('Universal')

    def __call__(self, task: Task):
        data_file_path = task.get_file_path()
        content = copy.deepcopy(task.get_prev_content())

        cap = cv2.VideoCapture(data_file_path)
        _, frame = cap.read()
        content = {'frame': EncodeOps.encode_image(frame)} if content is None \
            else {**content, 'frame': EncodeOps.encode_image(frame)}

        result = self.infer(content)
        result.pop('frame', None)

        task.set_current_content(result)

        return task

    def infer(self, input_ctx):
        assert self.processor, 'No universal processor defined!'

        with Timer(f'Universal Processor'):
            output_ctx = self.processor(input_ctx)

        return output_ctx
