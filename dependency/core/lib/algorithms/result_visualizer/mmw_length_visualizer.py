import abc
from core.lib.common import ClassFactory, ClassType
from core.lib.content import Task

from .curve_visualizer import CurveVisualizer

__all__ = ('MMWLengthVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='mmw_length')
class MMWLengthVisualizer(CurveVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __call__(self, task: Task):
        return {self.variables[0]: task.get_dag().get_node('mmw-detection').service.get_content_data()}
