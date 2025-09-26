import librosa

import time

import numpy as np
import torch
from torchvision.models import resnet34

from core.lib.common import LOGGER, Context


class AudioClassification:
    def __init__(self, weights, device, warmup_iters=3, warmup_seconds=4):
        self.sound_categories = [
            "Other (其他声音)",
            "Car Horn (喇叭声)",
            "Drilling (钻孔声)",
            "Engine Idling (引擎声)",
            "Jackhammer (重型机械声)",
            "Siren (警报声)",
        ]

        self.num_class = 10

        self.model_path = Context.get_file_path(weights)
        self.device = torch.device(device)

        self.model = self.load_model()
        self.warmup(iters=warmup_iters, seconds=warmup_seconds)

    def __call__(self, data, metadata):
        index = self.infer(data)
        index = index.item()
        index = [0, 1, 0, 0, 2, 3, 0, 4, 5, 0][index]

        return index

    @torch.inference_mode()
    def infer(self, data):
        data = self.load_data(data)
        data = torch.tensor(data, dtype=torch.float32, device=self.device)

        output = self.model(data)
        result = torch.nn.functional.softmax(output, dim=1)
        result = result.data.cpu().numpy()

        lab = np.argsort(result)[0][-1]
        return lab

    def load_data(self, data):
        data = np.frombuffer(data, dtype=np.short) / np.iinfo(np.short).max
        spec_mag = librosa.feature.melspectrogram(y=data * 1.0, sr=16000, hop_length=256).astype(np.float32)
        mean = np.mean(spec_mag, 0, keepdims=True)
        std = np.std(spec_mag, 0, keepdims=True)
        spec_mag = (spec_mag - mean) / (std + 1e-5)
        spec_mag = spec_mag[np.newaxis, np.newaxis, :]

        # print(spec_mag.shape)
        # [1, 1, 128, 251] -> [1, 3, 128, 251]
        spec_mag = np.repeat(spec_mag, 3, axis=1)

        return spec_mag

    def load_model(self):
        LOGGER.debug('Loading model start ..')

        model = resnet34(num_classes=self.num_class)
        model.load_state_dict(torch.load(self.model_path))
        model.to(self.device)
        model.eval()

        LOGGER.debug('Loading model completed')
        return model

    @torch.inference_mode()
    def warmup(self, iters=3, seconds=4):
        """
        The preheating includes two parts:

            1) librosa path: Build Mel filters, FFT framework, etc., and cache them

            2) Model path: Let cudnn/MKL select and cache the optimal operators, and warm up the weights
        """
        LOGGER.debug(f'Warm-up start: iters={iters}, seconds={seconds}')

        # —— 1) Preheat Feature Extraction (librosa)
        # Trigger a complete execution of melspectrogram with all zeros virtual audio
        dummy_pcm = np.zeros(int(16000 * seconds), dtype=np.int16).tobytes()
        _ = self.load_data(dummy_pcm)  # Not for results, only for building cache

        # —— 2) Preheat Model (Helpful for both GPU and CPU, more noticeable on GPU)
        dummy_spec = torch.zeros((1, 3, 128, 251), dtype=torch.float32, device=self.device)

        if self.device.type == 'cuda':
            torch.cuda.synchronize()

        for _ in range(max(1, iters)):
            _ = self.model(dummy_spec)
            if self.device.type == 'cuda':
                # Wait for GPU to complete, ensure it is truly preheated
                torch.cuda.synchronize()

        LOGGER.debug('Warm-up done')
