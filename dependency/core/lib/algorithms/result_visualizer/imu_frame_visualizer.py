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

    @staticmethod
    def _compute_equal_limits(P, pad_ratio=0.05):
        """
        Calculate the proportional (cubic) coordinate axis range to center the curve without stretching.

        pad_ratio is the margin ratio, to avoid edge contact.
        """
        if P.size == 0:
            return (-1, 1), (-1, 1), (-1, 1)

        x_min, y_min, z_min = np.nanmin(P[:, 0]), np.nanmin(P[:, 1]), np.nanmin(P[:, 2])
        x_max, y_max, z_max = np.nanmax(P[:, 0]), np.nanmax(P[:, 1]), np.nanmax(P[:, 2])

        cx = 0.5 * (x_min + x_max)
        cy = 0.5 * (y_min + y_max)
        cz = 0.5 * (z_min + z_max)

        rx = max(1e-9, (x_max - x_min) * 0.5)
        ry = max(1e-9, (y_max - y_min) * 0.5)
        rz = max(1e-9, (z_max - z_min) * 0.5)
        r = max(rx, ry, rz)

        r *= (1.0 + pad_ratio)

        return (cx - r, cx + r), (cy - r, cy + r), (cz - r, cz + r)

    def draw_imu_trajectory(self, input_data):
        process_data = np.asarray(input_data, dtype=np.float32)

        self.line.set_data_3d(process_data[:, 0], process_data[:, 1], process_data[:, 2], )

        xlim, ylim, zlim = self._compute_equal_limits(process_data, pad_ratio=0.05)
        self.ax.set_xlim3d(*xlim)
        self.ax.set_ylim3d(*ylim)
        self.ax.set_zlim3d(*zlim)

        self.canvas.draw()
        buf = np.frombuffer(self.canvas.tostring_rgb(), dtype=np.uint8)
        h, w, _ = self._img.shape
        np.copyto(self._img.reshape(-1), buf[: h * w * 3])
        return self._img.copy()[..., ::-1]

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
