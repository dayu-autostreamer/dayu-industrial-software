import abc
from typing import Tuple
import cv2
import numpy as np
import wave

from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER
from core.lib.content import Task

from .image_visualizer import ImageVisualizer

__all__ = ('AudioFrameVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='audio_frame')
class AudioFrameVisualizer(ImageVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.audio_service = kwargs.get('audio_service', None)

        # Category labels used as plot titles
        self.sound_categories = [
            "其他声音",
            "喇叭声",
            "钻孔声",
            "引擎声",
            "重型机械声",
            "警报声",
        ]

        import matplotlib
        # Ensure non-interactive backend to avoid GUI overhead
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        try:
            plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
        except Exception:
            pass

        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

        # Persistent Matplotlib objects
        self._plt = plt
        self.fig = plt.figure(figsize=(4, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)

        self._im = self.ax.imshow(
            np.zeros((2, 2), dtype=np.float32),
            origin='lower',
            aspect='auto',
            interpolation='nearest',
            vmin=-1.0, vmax=1.0  # normalized range we map to
        )
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Frequency (Hz)")
        self.ax.set_axis_off()
        self.ax.set_title("")  # will set per-call
        self.fig.tight_layout(pad=0.)

        # Draw once to initialize canvas size, then preallocate output buffer
        self.canvas.draw()
        w, h = self.canvas.get_width_height()
        self._img = np.empty((h, w, 3), dtype=np.uint8)

        # Cache function refs to avoid repeated global lookups
        import librosa
        self._librosa = librosa
        self._amplitude_to_db = librosa.amplitude_to_db

        # STFT config defaults (per-call we can recompute hop based on framerate)
        self._n_fft = 4096
        self._win_ms = 0.05  # 50 ms windows
        self._overlap_ratio = 0.75  # 75% overlap

    @staticmethod
    def _norm_neg1_to_1(arr: np.ndarray) -> np.ndarray:
        """Normalize array to [-1, 1] robustly; handles constant arrays."""
        a_min = np.min(arr)
        a_max = np.max(arr)
        if not np.isfinite(a_min) or not np.isfinite(a_max):
            return np.zeros_like(arr, dtype=np.float32)
        rng = a_max - a_min
        if rng <= 1e-12:
            return np.zeros_like(arr, dtype=np.float32)
        return (2.0 * (arr - a_min) / rng - 1.0).astype(np.float32)

    def _compute_stft(self, mono: np.ndarray, framerate: int) -> Tuple[np.ndarray, float, float]:
        """
        Compute linear-frequency STFT magnitude (in dB, then normalized to [-1,1]).
        Returns (norm_spec, time_extent, freq_extent_max).
        """
        # Window and hop in samples
        win_length = max(1, int(self._win_ms * framerate))
        hop_length = max(1, int(win_length * (1.0 - self._overlap_ratio)))

        # STFT -> magnitude -> dB
        stft = self._librosa.stft(mono.astype(np.float32), n_fft=self._n_fft,
                                  hop_length=hop_length, win_length=win_length)
        mag = np.abs(stft)
        spec_db = self._amplitude_to_db(mag, ref=np.max)  # scale relative to max magnitude
        spec_norm = self._norm_neg1_to_1(spec_db)

        # X axis extent in seconds; Y axis 0..Nyquist in Hz for linear display
        n_frames = spec_norm.shape[1]
        duration_sec = len(mono) / float(framerate) if framerate > 0 else 0.0
        # Time per hop:
        frame_hop_sec = hop_length / float(framerate) if framerate > 0 else 0.0
        time_max = frame_hop_sec * n_frames

        # Max frequency shown by STFT (Nyquist)
        freq_max = framerate / 2.0

        return spec_norm, time_max, freq_max

    def _render_to_rgb(self) -> np.ndarray:
        """Render persistent figure to an RGB numpy array without touching disk."""
        self.canvas.draw()
        buf = np.frombuffer(self.canvas.tostring_rgb(), dtype=np.uint8)
        h, w, _ = self._img.shape
        np.copyto(self._img.reshape(-1), buf[: h * w * 3])
        return self._img  # RGB view (do not modify in place outside)

    def draw_audio_spec(self, data: bytes, framerate: int, nchannels: int, title: str) -> np.ndarray:
        """
        Update the persistent image with the new spectrogram and return an RGB array.
        """
        # Convert to mono float32
        buffer = np.frombuffer(data, dtype=np.int16)
        if nchannels == 2:
            # Average L/R into mono
            buffer = ((buffer[::2].astype(np.float32) + buffer[1::2].astype(np.float32)) * 0.5)
        else:
            buffer = buffer.astype(np.float32)

        if buffer.size == 0 or framerate <= 0:
            # Graceful fallback: empty image with neutral content
            self._im.set_data(np.zeros((2, 2), dtype=np.float32))
            self._im.set_extent((0, 1, 0, 1))
            self.ax.set_title(title)
            return self._render_to_rgb().copy()

        # Compute normalized spectrogram and axis extents
        spec, t_max, f_max = self._compute_stft(buffer, framerate)

        # Update image data and extent (time on X, frequency on Y)
        # extent = (xmin, xmax, ymin, ymax)
        self._im.set_data(spec)
        self._im.set_extent((0.0, max(t_max, 1e-6), 0.0, max(f_max, 1e-6)))

        # Update labels/title only (cheap)
        self.ax.set_title(title, fontsize=16, color='red')

        # Render to RGB numpy array
        return self._render_to_rgb().copy()

    def __call__(self, task: Task):
        try:
            if self.audio_service:
                content = task.get_dag().get_node(self.audio_service).service.get_content_data()
            else:
                content = task.get_last_content()
        except Exception:
            content = task.get_last_content()

        # Read raw audio once per call
        file_path = task.get_file_path()
        try:
            with wave.open(file_path, 'rb') as f:
                params = f.getparams()
                nchannels, sampwidth, framerate, nframes = params[:4]
                data = f.readframes(nframes)

            # Draw spectrogram → RGB
            title = self.sound_categories[int(content)] if isinstance(content, (int, np.integer)) else str(content)
            image_rgb = self.draw_audio_spec(data, framerate, nchannels, title)

            # Convert RGB → BGR for current EncodeOps (which expects BGR)
            image_bgr = image_rgb[..., ::-1]
            base64_data = EncodeOps.encode_image(image_bgr)

        except Exception as e:
            # Fallback image if anything goes wrong
            base64_data = EncodeOps.encode_image(cv2.imread(self.default_visualization_image))
            LOGGER.warning(f'Audio visualization failed: {str(e)}')
            LOGGER.exception(e)

        return {'image': base64_data}
