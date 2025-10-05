import abc

from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER
from core.lib.content import Task

from .image_visualizer import ImageVisualizer

__all__ = ('EdgeFrameVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='edge_frame')
class EdgeFrameVisualizer(ImageVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.edge_service = kwargs.get('edge_service', None)

    def draw_edges(self, image, lps, rps):
        import cv2
        cv2.putText(image, f'lps:{lps}  rps:{rps}', (50, 50), cv2.FONT_HERSHEY_COMPLEX, 2.0, (208, 2, 27), 5)
        if lps and lps>0:
            cv2.line(image, (lps, 300), (lps, 500), (0, 0, 255), 4, 8)
        if rps and rps>0:
            cv2.line(image, (rps, 300), (rps, 500), (0, 0, 255), 4, 8)

        return image

    def __call__(self, task: Task):
        import cv2
        try:
            if self.edge_service:
                content = task.get_dag().get_node(self.edge_service).service.get_content_data()
            else:
                content = task.get_last_content()
        except Exception as e:
            content = task.get_last_content()

        try:
            file_path = task.get_file_path()
            frame = cv2.VideoCapture(file_path).read()[1]
            image = EncodeOps.decode_image(frame)
            lps = content['lps'] if 'lps' in content else 0
            rps = content['rps'] if 'rps' in content else 0
            image = self.draw_edges(image, lps, rps)

            base64_data = EncodeOps.encode_image(image)
        except Exception as e:
            base64_data = EncodeOps.encode_image(
                cv2.imread(self.default_visualization_image)
            )
            LOGGER.warning(f'Video visualization fetch failed: {str(e)}')
            LOGGER.exception(e)

        return {self.variables[0]: base64_data}
