import abc
import numpy as np
from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER
from core.lib.content import Task
from .base_trigger import BaseTrigger

__all__ = ('AbnormalAudioTrigger',)


@ClassFactory.register(ClassType.EVENT_TRIGGER, alias='abnormal_audio')
class AbnormalAudioTrigger(BaseTrigger, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __call__(self, task: Task):
        # Return the detailed time of each stage
        if task.get_last_content() == 5:
            return True, {}
        return False, {}

