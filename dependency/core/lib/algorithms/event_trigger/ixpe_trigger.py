import abc
import numpy as np
from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER
from core.lib.content import Task
from .base_trigger import BaseTrigger

__all__ = ('IxpeTrigger',)


@ClassFactory.register(ClassType.EVENT_TRIGGER, alias='video')
class IxpeTrigger(BaseTrigger, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.LThreshold = kwargs.get('LThreshold', None)
        self.RThreshold = kwargs.get('RThreshold', None)

    def __call__(self, task: Task):
        # 返回各阶段的详细用时
        content = task.get_last_content()
        lps = content['lps'] if 'lps' in content else 0
        rps = content['rps'] if 'rps' in content else 0
        ans = 0
        if self.LThreshold is not None and 0 < lps < self.LThreshold:
            ans |= 1
        if self.RThreshold is not None and rps > 0 and rps > self.RThreshold:
            ans |= 2
        if ans == 1:
            return True,{'左边缘偏移,位置': lps}
        elif ans == 2:
            return True, {'右边缘偏移,位置': rps}
        elif ans == 3:
            return True, {'左边缘偏移,位置': lps,'右边缘偏移,位置': rps}
        else:
            return False,{}

