import abc
import numpy as np
from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER
from core.lib.content import Task
from .base_trigger import BaseTrigger

__all__ = ('TotalTimeTrigger',)


@ClassFactory.register(ClassType.EVENT_TRIGGER, alias='total_time')
class TotalTimeTrigger(BaseTrigger, abc.ABC):
    frame_history = []
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.threshold = kwargs.get('threshold', None)

    def __call__(self, task: Task):
        # 返回各阶段的详细用时
        if task.calculate_total_time() < self.threshold:
            return False, {}
        return True, {'延迟信息': task.get_delay_info()}

