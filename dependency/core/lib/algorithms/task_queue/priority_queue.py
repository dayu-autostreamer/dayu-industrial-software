import abc
import threading
from queue import PriorityQueue as PQ

from core.lib.common import ClassFactory, ClassType
from core.lib.content import Task
from .base_queue import BaseQueue

__all__ = ('PriorityQueue',)


@ClassFactory.register(ClassType.PRO_QUEUE, alias='priority')
class PriorityQueue(BaseQueue, abc.ABC):
    def __init__(self):
        self._queue = PQ()
        self.lock = threading.Lock()

        self._MAX_SIZE = 10

    def put(self, task: Task) -> None:
        with self.lock:
            task.record_priority_timestamp(is_enter=True)
            self._queue.put(task)

    def get(self):
        with self.lock:
            if self._queue.empty():
                return None
            task = self._queue.get()
            task.record_priority_timestamp(is_enter=False)
            return task

    def size(self) -> int:
        with self.lock:
            return self._queue.qsize()

    def empty(self) -> bool:
        return self._queue.empty()
