import abc
import os
import cv2
import numpy as np
import wave
import librosa
import matplotlib.pyplot as plt

from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER
from core.lib.content import Task

from .image_visualizer import ImageVisualizer

__all__ = ('AudioFrameVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='audio_frame')
class AudioFrameVisualizer(ImageVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.audio_service = kwargs.get('audio_service', None)

        self.sound_categories = [
            "Other (其他声音)"
            "Car Horn (喇叭声)",
            "Drilling (钻孔声)",
            "Engine Idling (引擎声)",
            "Jackhammer (重型机械声)",
            "Siren (警报声)",
        ]

    def draw_audio_spec(self, data, framerate, nchannels, result):

        def cal_norm(nparray):
            # [-1, 1]
            return 2 * (nparray - np.min(nparray)) / (np.max(nparray) - np.min(nparray)) - 1

        databuffer = np.frombuffer(data, dtype=np.short)
        if nchannels == 2:
            databuffer = (databuffer[::2] + databuffer[1::2]) / 2

        window_size = int(0.05 * framerate)
        overlap = int(window_size * (1 - 0.75))
        n_fft = 4096

        stft = librosa.stft(databuffer.astype(np.float32), n_fft=n_fft, hop_length=overlap, win_length=window_size)

        # 转换为分贝 (dB) 单位
        log_spectrogram = librosa.amplitude_to_db(np.abs(stft))
        # 归一化为 [-1, 1]
        log_spectrogram = cal_norm(log_spectrogram)

        # 画出频谱图
        librosa.display.specshow(log_spectrogram, sr=framerate, win_length=window_size, hop_length=overlap,
                                 x_axis='time', y_axis='linear')
        # 添加颜色条
        plt.colorbar(format='%+2.0f', ticks=[-1, 1])
        plt.title(result, fontsize=25, color='red')

        plt.savefig('audio.png', bbox_inches='tight', pad_inches=0.0)
        plt.close()
        image = cv2.imread('audio.png')
        os.remove(os.path.abspath('audio.png'))

        return image

    def __call__(self, task: Task):
        try:
            if self.audio_service:
                content = task.get_dag().get_node(self.audio_service).service.get_content_data()
            else:
                content = task.get_last_content()
        except Exception as e:
            content = task.get_last_content()
        file_path = task.get_file_path()

        try:
            with wave.open(file_path, 'r') as f:
                params = f.getparams()
                nchannels, sampwidth, framerate, nframes = params[:4]
                data = f.readframes(nframes)

            image = self.draw_audio_spec(data, framerate, nchannels, self.sound_categories[content])
            base64_data = EncodeOps.encode_image(image)
        except Exception as e:
            base64_data = EncodeOps.encode_image(
                cv2.imread(self.default_visualization_image)
            )
            LOGGER.warning(f'Video visualization fetch failed: {str(e)}')
            LOGGER.exception(e)

        return {'image': base64_data}
