import abc
import numpy as np
from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER, Context
from core.lib.content import Task
import cv2

from .image_visualizer import ImageVisualizer

__all__ = ('MMWaveFrameVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='mmwave_frame')
class MMWaveFrameVisualizer(ImageVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def plot_mmwave_data(self, range_doppler: np.ndarray):
        # Normalize to 0-255 for visualization
        rd_mag = range_doppler - range_doppler.min()
        if rd_mag.max() > 0:
            rd_norm = (rd_mag / rd_mag.max() * 255.0).astype(np.uint8)
        else:
            rd_norm = np.zeros_like(rd_mag, dtype=np.uint8)

        # Create color heatmap (range x doppler). Transpose to (range, doppler) for intuitive axes
        img_gray = rd_norm.T  # (rangeBins, dopplerBins)
        img_color = cv2.applyColorMap(img_gray, cv2.COLORMAP_JET)

        # Optionally resize for better readability
        h, w = img_color.shape[:2]
        scale = 2 if max(h, w) < 256 else 1
        if scale != 1:
            img_color = cv2.resize(img_color, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)

        # Add simple annotations
        try:
            txt_color = (255, 255, 255)
            cv2.putText(img_color, 'Range-Doppler Map (Tx0-Rx0)', (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, txt_color, 2)
        except Exception as e:
            LOGGER.debug(f'Annotation failed: {e}')

        return img_color

    def __call__(self, task: Task):
        try:
            content = task.get_last_content()
            rd = content[0]['range_doppler']
            image = self.plot_mmwave_data(np.array(rd))
            base64_data = EncodeOps.encode_image(image)
        except Exception as e:
            base64_data = EncodeOps.encode_image(
                cv2.imread(self.default_visualization_image)
            )
            LOGGER.warning(f'Video visualization fetch failed: {str(e)}')
            LOGGER.exception(e)
        return {self.variables[0]: base64_data}
