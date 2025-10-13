import abc
from core.lib.common import ClassFactory, ClassType
from core.lib.content import Task

from .curve_visualizer import CurveVisualizer

__all__ = ('MMWaveLengthVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='mmwave_length')
class MMWaveLengthVisualizer(CurveVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __call__(self, task: Task):
        content = task.get_last_content()
        distance = content[0]['distance'] if content else 0.0

        return {self.variables[0]: distance}
