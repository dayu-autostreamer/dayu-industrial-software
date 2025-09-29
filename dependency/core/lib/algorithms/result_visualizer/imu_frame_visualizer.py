import abc
import os
import cv2
import numpy as np

from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER
from core.lib.content import Task

from .image_visualizer import ImageVisualizer

__all__ = ('IMUFrameVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='imu_frame')
class IMUFrameVisualizer(ImageVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

        self.imu_service = kwargs.get('imu_service', None)

        self.fig = plt.figure()
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.fig.tight_layout(pad=0)
        (self.line,) = self.ax.plot([], [], [], linewidth=0.8, antialiased=False)
        self.canvas.draw()
        w, h = self.canvas.get_width_height()
        self._img = np.empty((h, w, 3), dtype=np.uint8)

    def draw_imu_trajectory(self, input_data):
        process_data = np.asarray(input_data, dtype=np.float32)

        self.line.set_data_3d(process_data[:, 0], process_data[:, 1], process_data[:, 2], )
        self.canvas.draw()
        buf = np.frombuffer(self.canvas.tostring_rgb(), dtype=np.uint8)
        h, w, _ = self._img.shape
        np.copyto(self._img.reshape(-1), buf[: h * w * 3])
        return self._img.copy()

    def __call__(self, task: Task):
        try:
            if self.imu_service:
                content = task.get_dag().get_node(self.imu_service).service.get_content_data()
            else:
                content = task.get_last_content()
        except Exception as e:
            content = task.get_last_content()

        try:
            image = self.draw_imu_trajectory(content)
            base64_data = EncodeOps.encode_image(image)
        except Exception as e:
            base64_data = EncodeOps.encode_image(
                cv2.imread(self.default_visualization_image)
            )
            LOGGER.warning(f'Video visualization fetch failed: {str(e)}')
            LOGGER.exception(e)

        return {'image': base64_data}
