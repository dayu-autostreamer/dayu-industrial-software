import numpy as np

from .processor import Processor

from core.lib.estimation import Timer
from core.lib.content import Task
from core.lib.common import Context, ClassFactory, ClassType


@ClassFactory.register(ClassType.PROCESSOR, alias='imu_tracker_processor')
class IMUTrackerProcessor(Processor):
    def __init__(self):
        super().__init__()

        self.tracker = Context.get_instance('IMUTracker')

    def __call__(self, task: Task):
        data_file_path = task.get_file_path()

        data = np.load(data_file_path)
        with Timer(f'IMU Tracker'):
            result = self.tracker(data)
        task.set_current_content(result)

        return task
