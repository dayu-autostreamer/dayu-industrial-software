import abc
from core.lib.common import ClassFactory, ClassType
from core.lib.content import Task

from .curve_visualizer import CurveVisualizer

__all__ = ('IMUTrajectoryLengthVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='imu_trajectory_length')
class IMUTrajectoryLengthVisualizer(CurveVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __call__(self, task: Task):
        return {self.variables[0]: len(task.get_last_content())}
