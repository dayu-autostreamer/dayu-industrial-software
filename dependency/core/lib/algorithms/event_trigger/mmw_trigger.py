import abc
import numpy as np
from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER
from core.lib.content import Task
from .base_trigger import BaseTrigger

__all__ = ('MmwTrigger',)


@ClassFactory.register(ClassType.EVENT_TRIGGER, alias='mmw')
class MmwTrigger(BaseTrigger, abc.ABC):
    frame_history = []
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.window_num = 5
        self.window_len = 30
        self.threshold = 0.25

    def __call__(self, task: Task):
        single_res = task.get_dag().get_node('mmw-detection').service.get_content_data()
        MmwTrigger.frame_history.append(single_res)
        cnt = 0
        if len(MmwTrigger.frame_history) < self.window_len * self.window_num:
            return False
        for i in range(self.window_num):
            frame_window = MmwTrigger.frame_history[-(self.window_len+1)*i:-self.window_len*i]
            if task.get_task_id() == 508:
                LOGGER.info(frame_window)
                LOGGER.info(np.var(frame_window))
            if np.var(frame_window) > self.threshold:
                cnt += 1
        LOGGER.debug(f'task:{task.get_task_id()},res:{single_res},w:{cnt}')
        if cnt >= (self.window_num+1)/2:
            return True
        else:
            return False
