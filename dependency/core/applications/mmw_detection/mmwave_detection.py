import ctypes
from typing import List
import numpy as np

from core.lib.common import Context, LOGGER

class MMWaveDetection:
    def __init__(self):
        # 初始化工作:读取配置
        # 在计算时,所使用的毫米波配置只有c.rangeFFTWindow 和 c.dopplerFFTWindow.所以可以不用在这里引入配置类
        LOGGER.debug(f'initializing MMWave application model!!')
        self.rangeFFTWindow = np.hamming
        self.dopplerFFTWindow = np.ones

    def __call__(self, data):
        # LOGGER.debug('start infer ..')

        return self.process(data)

    def process(self, framedata: np.ndarray) -> float:
        range_result = self.range_fft_frame(frame_data=framedata)

        # empirical scaling factor
        strength_ratio = 0.1

        # get phase
        ang = np.angle(range_result[0, 0, :, 0])
        distance = ang / 2 / np.pi * 5

        return np.mean(distance) / strength_ratio

    def awgn(self,x, snr, seed=7):
        np.random.seed(seed)
        t_snr = 10 ** (snr / 10.0)
        xpower = np.sum(x ** 2) / np.size(x)
        npower = xpower / t_snr
        noise = np.random.randn(np.size(x)) * np.sqrt(npower)
        return x + noise.reshape(x.shape)

    # frame_data.shape: (numTx, numRx, numChirpPerFramePerTx, numSamplePerChirp)
    # ret.shape:        (numTx, numRx, numChirpPerFramePerTx, numSamplePerChirp)
    def range_fft_frame(self, frame_data: np.ndarray) -> np.ndarray:
        ret = np.zeros_like(frame_data)
        tmp = np.zeros([frame_data.shape[-1]], dtype=frame_data.dtype)
        window = self.rangeFFTWindow(tmp.shape[0])

        for iTx in range(frame_data.shape[0]):
            for iRx in range(frame_data.shape[1]):
                for iChirp in range(frame_data.shape[2]):
                    tmp[:] = frame_data[iTx, iRx, iChirp, :]
                    tmp[:] = tmp[:] - np.mean(tmp)
                    tmp[:] = tmp * window
                    tmp[:] = np.fft.fft(tmp, tmp.shape[0])
                    ret[iTx, iRx, iChirp, :] = tmp

        return ret

    # range_bin.shape: (numTx, numRx, numChirpPerFramePerTx, numSamplePerChirp//2)
    # ret.shape: (numTx, numRx, numChirpPerFramePerTx, numSamplePerChirp//2)
    def doppler_fft_frame(self, range_bin: np.ndarray, fill_zdop: bool = True) -> np.ndarray:
        # range_bin.shape: (numTx, numRx, numSamplePerChirp//2, numChirpPerFramePerTx)
        range_bin_transp = range_bin.transpose([0, 1, 3, 2])

        ret = np.zeros(range_bin.shape, dtype=range_bin.dtype)
        tmp = np.zeros([range_bin_transp.shape[-1]], dtype=range_bin.dtype)
        window = self.dopplerFFTWindow(tmp.shape[-1])

        for iTx in range(range_bin_transp.shape[0]):
            for iRx in range(range_bin_transp.shape[1]):
                for iSample in range(range_bin_transp.shape[2]):
                    tmp[:] = range_bin_transp[iTx, iRx, iSample, :]
                    tmp[:] = tmp * window
                    if fill_zdop:
                        tmp[:] = tmp - np.mean(tmp)
                    tmp[:] = np.fft.fft(tmp, tmp.shape[0])
                    tmp[:] = np.fft.fftshift(tmp)

                    # 0值 : 均匀填充
                    # 0频率分量填充
                    if fill_zdop:
                        zpoint = tmp.shape[-1] // 2
                        tmp[zpoint] = np.average([tmp[zpoint - 1], tmp[zpoint + 1]])

                    ret[iTx, iRx, :, iSample] = tmp

        return ret
