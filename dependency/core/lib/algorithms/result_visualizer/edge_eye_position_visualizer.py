import abc
from core.lib.common import ClassFactory, ClassType
from core.lib.content import Task

from .curve_visualizer import CurveVisualizer

__all__ = ('EdgeEyePositionVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='edge_eye_position')
class EdgeEyePositionVisualizer(CurveVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __call__(self, task: Task):
        return {
            self.variables[0]: task.get_last_content()['lps'],
            self.variables[1]: task.get_last_content()['rps']
        }
