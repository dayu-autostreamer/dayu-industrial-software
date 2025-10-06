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
        return {self.variables[0]: task.get_dag().get_node('mmwave-detection').service.get_content_data()}
