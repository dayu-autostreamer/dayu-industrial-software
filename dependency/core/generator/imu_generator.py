from .generator import Generator
from core.lib.content import Task

from core.lib.common import ClassType, ClassFactory, Context, LOGGER


@ClassFactory.register(ClassType.GENERATOR, alias='imu')
class IMUGenerator(Generator):
    def __init__(self, source_id: int, source_url: str,
                 source_metadata: dict, dag: list):
        super().__init__(source_id, source_metadata, dag)
        self.imu_data_source = source_url

    def submit_task_to_controller(self, cur_task):
        self.record_total_start_ts(cur_task)
        super().submit_task_to_controller(cur_task)

    def run(self):
        # initialize with default schedule policy
        self.after_schedule_operation(self, None)

        while True:
            self.data_getter(self)

            self.request_schedule_policy()
