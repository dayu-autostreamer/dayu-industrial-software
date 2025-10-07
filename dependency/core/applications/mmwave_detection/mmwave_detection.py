import numpy as np

from core.lib.common import Context, convert_ndarray_to_list

from .mmwave_config import get_config, MMWaveConfig
from .data_reader import FrameIter


class MMWaveDetection:
    def __init__(self):
        config_path = Context.get_file_path(Context.get_parameter('MMWAVE_CONFIG'))
        with open(config_path, 'r') as fp:
            mmwaveConfigContent = fp.read()
        self.cfg = get_config(mmwaveConfigContent)

        self.rangeFFTWindow = np.hamming
        self.dopplerFFTWindow = np.ones

    def __call__(self, file_list: 'list[str]'):
        fit = FrameIter(self.cfg, file_list)
        result = []
        while True:
            try:
                frame_data = next(fit)
            except StopIteration:
                break
            result.append(self.process(frame_data))
        return result

    def process(self, frame_data: np.ndarray):
        range_fft = self.range_fft_frame(frame_data=frame_data)

        # empirical scaling factor
        strength_ratio = 0.1
        # get phase
        ang = np.angle(range_fft[0, 0, :, 0])
        distance = ang / 2 / np.pi * 5
        distance = np.mean(distance) / strength_ratio

        return convert_ndarray_to_list({'config': self.cfg.to_jsons(), 'distance': distance})

    def awgn(self, x, snr, seed=7):
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
