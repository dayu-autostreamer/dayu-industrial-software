import abc

from core.lib.content import Task


class BaseTrigger(metaclass=abc.ABCMeta):
    def __init__(self, **kwargs):
        pass

    def __call__(self, task: Task):
        raise NotImplementedError
