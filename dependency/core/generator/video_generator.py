from .generator import Generator
from core.lib.content import Task

from core.lib.common import ClassType, ClassFactory, Context, LOGGER


@ClassFactory.register(ClassType.GENERATOR, alias='video')
class VideoGenerator(Generator):
    def __init__(self, source_id: int, source_type: str,
                 priority_coefficients: dict,
                 source_importance: int, source_url: str,
                 source_metadata: dict, dag: list):
        super().__init__(source_id,
                         source_type=source_type,
                         priority_coefficients=priority_coefficients,
                         source_importance=source_importance,
                         metadata=source_metadata,
                         task_dag=dag)
        self.video_data_source = source_url

        self.frame_filter = Context.get_algorithm('GEN_FILTER')
        self.frame_process = Context.get_algorithm('GEN_PROCESS')
        self.frame_compress = Context.get_algorithm('GEN_COMPRESS')
        self.getter_filter = Context.get_algorithm('GEN_GETTER_FILTER')

    def submit_task_to_controller(self, cur_task):
        self.record_total_start_ts(cur_task)
        super().submit_task_to_controller(cur_task)

    def run(self):
        # initialize with default schedule policy
        self.after_schedule_operation(self, None)

        while True:
            if not self.getter_filter(self):
                LOGGER.info('[Filter Getter] step to next round of getter.')
                continue
            self.data_getter(self)

            self.request_schedule_policy()
