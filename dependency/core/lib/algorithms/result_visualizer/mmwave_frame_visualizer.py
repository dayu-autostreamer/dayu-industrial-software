import abc
import numpy as np
from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER, FileOps
from core.lib.content import Task
import cv2
import os
import json

from .image_visualizer import ImageVisualizer

__all__ = ('MMWaveFrameVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='mmwave_frame')
class MMWaveFrameVisualizer(ImageVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.rangeFFTWindow = np.hamming
        self.dopplerFFTWindow = np.ones

    def plot_mmwave_data(self, frame_data: np.ndarray):
        range_fft = self.range_fft_frame(frame_data=frame_data)

        numSamplePerChirp = 512
        half = numSamplePerChirp // 2
        doppler_fft = self.doppler_fft_frame(range_bin=range_fft[..., :half])
        rd = doppler_fft[0, 0, :, :]
        rd_mag = 20 * np.log10(np.abs(rd) + 1e-12)

        # Normalize to 0-255 for visualization
        rd_mag = rd_mag - rd_mag.min()
        if rd_mag.max() > 0:
            rd_norm = (rd_mag / rd_mag.max() * 255.0).astype(np.uint8)
        else:
            rd_norm = np.zeros_like(rd_mag, dtype=np.uint8)

        # Create color heatmap (range x doppler). Transpose to (range, doppler) for intuitive axes
        img_gray = rd_norm.T  # (rangeBins, dopplerBins)
        img_color = cv2.applyColorMap(img_gray, cv2.COLORMAP_JET)

        # Optionally resize for better readability
        h, w = img_color.shape[:2]
        scale = 2
        img_color = cv2.resize(img_color, (max(h,w) * scale, max(h,w) * scale), interpolation=cv2.INTER_NEAREST)

        # Add simple annotations
        try:
            txt_color = (255, 255, 255)
            cv2.putText(img_color, 'Range-Doppler Map (Tx0-Rx0)', (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 2, txt_color, 4)
        except Exception as e:
            LOGGER.debug(f'Annotation failed: {e}')

        return img_color

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

                    if fill_zdop:
                        zpoint = tmp.shape[-1] // 2
                        tmp[zpoint] = np.average([tmp[zpoint - 1], tmp[zpoint + 1]])

                    ret[iTx, iRx, :, iSample] = tmp

        return ret

    def __call__(self, task: Task):
        try:
            file_path = task.get_file_path()
            content = task.get_last_content()
            cfg = get_config(content[0]['config'])
            tmp_dir = f"mmwave_{task.get_source_id()}_{task.get_task_id()}_dir"
            FileOps.create_directory(tmp_dir)
            FileOps.unzip_file(file_path, tmp_dir)

            file_list = []
            for root, _, files in os.walk(tmp_dir):
                for fn in files:
                    if fn.lower().endswith('.bin'):
                        file_list.append(os.path.join(root, fn))
            # sort by filename to preserve order
            file_list.sort()
            fit = FrameIter(cfg, file_list)

            image = self.plot_mmwave_data(next(fit))
            base64_data = EncodeOps.encode_image(image)
            FileOps.remove_file(tmp_dir)
        except Exception as e:
            base64_data = EncodeOps.encode_image(
                cv2.imread(self.default_visualization_image)
            )
            LOGGER.warning(f'Video visualization fetch failed: {str(e)}')
            LOGGER.exception(e)
        return {self.variables[0]: base64_data}


class FrameIter:
    def __init__(self, c: 'MMWaveConfig', files: 'list[str]'):
        self.cfg = c
        self.frameSize = calcFrameSize_2Byte(c)
        self.currentFp = None

        self.files = files
        self.fileIdx = 0
        self.bufp = 0
        self.buf = np.array([], dtype=np.uint16)

    def _nextFile(self):
        if len(self.files) == self.fileIdx:
            raise StopIteration

        self.bufp = 0
        self.buf = np.fromfile(
            file=self.files[self.fileIdx],
            dtype=np.uint16
        )

        self.fileIdx += 1

    def __iter__(self):
        if self.currentFp is not None:
            self.currentFp.close()

        self.fileIdx = 0
        self._nextFile()

        return self

    def __next__(self):
        bufp = self.bufp
        frameSize = self.frameSize
        c = self.cfg

        ret = self.buf[bufp: bufp + frameSize]

        if ret.size != frameSize:
            self._nextFile()
            ret = np.concatenate([ret, self.buf[:frameSize - ret.size]])

            # the next file does not contain enough data
            if ret.size != frameSize:
                raise StopIteration

            self.bufp = frameSize - ret.size
        else:
            self.bufp += frameSize

        if self.cfg.calc_num_rx() == 1:
            ret = ret.reshape([-1, 2])[:, 0].reshape([-1])

        tmp = ret.reshape(-1, 4).astype(np.int16)

        # get complex
        ret = np.zeros([ret.size // 2], dtype=np.complex64)
        ret += tmp[:, 0:2].reshape(-1)
        ret += tmp[:, 2:4].reshape(-1).astype(np.complex64) * 1j

        # get normal form
        ret = ret.reshape([c.numChirpPerFramePerTx, c.calc_num_tx(), c.calc_num_rx(), c.numSamplePerChirp])
        ret = ret.transpose([1, 2, 0, 3])

        return ret


def calcFrameSize_2Byte(c: 'MMWaveConfig'):
    # Complex IQ
    sz = c.calc_num_rx() * c.calc_num_tx() * c.numChirpPerFramePerTx * c.numSamplePerChirp * 2
    return sz * 2 if 1 == c.calc_num_rx() else sz


class MMWaveConfig:
    def __init__(self):
        self.tx_pattern = 1
        self.rx_pattern = 1
        self.mimo_scheme = ''
        self.numSamplePerChirp = 512
        self.numChirpPerFramePerTx = 64
        self.numFrame = 10000
        self.framePeriodicity_msec = 0
        self.fslope_mhz_usec = 0
        self.ramptime_usec = 0
        self.idletime_usec = 0
        self.samp_rate_ksps = 0
        self.start_freq_ghz = 0

        self.rangeFFTWindow = np.hamming
        self.dopplerFFTWindow = np.ones
        return

    # calculate number of tx channels
    def calc_num_tx(self):
        return count_ones(int(self.tx_pattern, base=16))

    # calculate number of rx channels
    def calc_num_rx(self):
        return count_ones(int(self.rx_pattern, base=16))

    # calculate number of frames that tx transfers
    def calc_num_chirp_per_frame(self):
        return self.calc_num_tx() * self.numChirpPerFramePerTx

    # calculate wavelength of the carrier
    def calc_wavelength_meter(self):
        return 0.3 / self.start_freq_ghz

    # calculate the bandwidth within the sampling interval
    def calc_effective_bandw_ghz(self):
        return self.fslope_mhz_usec * (1 / self.samp_rate_ksps * 1000) * self.numSamplePerChirp / 1000

    # calculate the range resolution
    def calc_range_resolution_meter(self):
        return 0.15 / self.calc_effective_bandw_ghz()

    # calculate the maximum range the radar can detect
    def calc_max_range_meter(self):
        return self.calc_range_resolution_meter() * self.numSamplePerChirp / 2

    # calculate the velocity resolution
    def calc_velocity_resolution_meter_sec(self):
        singleChirpTime_usec = self.ramptime_usec + self.idletime_usec
        chirpLoopTime_usec = singleChirpTime_usec * self.calc_num_tx() if 'TDM' == self.mimo_scheme else singleChirpTime_usec

        return 10 ** 6 * self.calc_wavelength_meter() / 2 / (chirpLoopTime_usec * self.numChirpPerFramePerTx)

    # calculate the maximum velocity the radar can detect
    def calc_max_velocity_meter_sec(self):
        return self.calc_velocity_resolution_meter_sec() * self.numChirpPerFramePerTx

    # read radar configuration from json
    def from_jsons(self, mmwaveJsonFileContent) -> 'MMWaveConfig':
        # setupJsonObject = json.loads(setupJsonFileContent)
        mmwaveJsonObject = json.loads(mmwaveJsonFileContent)

        self.tx_pattern = get_at(mmwaveJsonObject, "mmWaveDevices.0.rfConfig.rlChanCfg_t.txChannelEn")
        self.rx_pattern = get_at(mmwaveJsonObject, "mmWaveDevices.0.rfConfig.rlChanCfg_t.rxChannelEn")
        self.mimo_scheme = get_at(mmwaveJsonObject, "mmWaveDevices.0.rfConfig.MIMOScheme")
        self.numSamplePerChirp = get_at(mmwaveJsonObject,
                                        "mmWaveDevices.0.rfConfig.rlProfiles.0.rlProfileCfg_t.numAdcSamples")
        self.numChirpPerFramePerTx = get_at(mmwaveJsonObject, "mmWaveDevices.0.rfConfig.rlFrameCfg_t.numLoops")
        self.numFrame = get_at(mmwaveJsonObject, "mmWaveDevices.0.rfConfig.rlFrameCfg_t.numFrames")
        self.framePeriodicity_msec = get_at(mmwaveJsonObject,
                                            "mmWaveDevices.0.rfConfig.rlFrameCfg_t.framePeriodicity_msec")
        self.fslope_mhz_usec = get_at(mmwaveJsonObject,
                                      "mmWaveDevices.0.rfConfig.rlProfiles.0.rlProfileCfg_t.freqSlopeConst_MHz_usec")
        self.ramptime_usec = get_at(mmwaveJsonObject,
                                    "mmWaveDevices.0.rfConfig.rlProfiles.0.rlProfileCfg_t.rampEndTime_usec")
        self.idletime_usec = get_at(mmwaveJsonObject,
                                    "mmWaveDevices.0.rfConfig.rlProfiles.0.rlProfileCfg_t.idleTimeConst_usec")
        self.samp_rate_ksps = get_at(mmwaveJsonObject,
                                     "mmWaveDevices.0.rfConfig.rlProfiles.0.rlProfileCfg_t.digOutSampleRate")
        self.start_freq_ghz = get_at(mmwaveJsonObject,
                                     "mmWaveDevices.0.rfConfig.rlProfiles.0.rlProfileCfg_t.startFreqConst_GHz")

        return self

    def from_json(self, mmwaveJsonFileName: str) -> 'MMWaveConfig':
        with open(mmwaveJsonFileName, 'r') as f:
            mmwaveJsonFileContent = f.read()

        return self.from_jsons(mmwaveJsonFileContent)


def count_ones(x):
    cnt = 0
    while (0 != x):
        if (x & 1) != 0:
            cnt = cnt + 1
        x = x >> 1
    return cnt


# default get_method: x[y]
def get_at(obj, path: str, get_method=lambda o, path_piece: o[path_piece]):
    path_pieces = path.split('.')
    path_pieces = list(filter(lambda x: '' != x, path_pieces))

    iter = obj
    for piece in path_pieces:
        try:
            iter = get_method(iter, piece)
        except:
            iter = get_method(iter, int(piece))

    return iter


# Get mmwave configuration and return
def get_config(mmwjsonContent: str) -> MMWaveConfig:
    return MMWaveConfig().from_jsons(mmwaveJsonFileContent=mmwjsonContent)
