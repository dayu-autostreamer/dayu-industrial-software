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
        self.imu_service = kwargs.get('imu_service', None)

    def draw_imu_trajectory(self, input_data):
        import matplotlib.pyplot as plt

        process_data = np.array(input_data)

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.plot3D(process_data[:, 0],
                  process_data[:, 1],
                  process_data[:, 2])

        plt.savefig('imu.png', bbox_inches='tight', pad_inches=0.0)
        plt.close(fig)

        image = cv2.imread('imu.png')
        os.remove(os.path.abspath('imu.png'))

        return image

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
