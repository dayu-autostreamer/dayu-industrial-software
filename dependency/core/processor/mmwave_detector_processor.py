import json
import numpy as np
from .processor import Processor

from core.lib.estimation import Timer
from core.lib.content import Task
from core.lib.common import Context
from core.lib.common import ClassFactory, ClassType


@ClassFactory.register(ClassType.PROCESSOR, alias='mmwave_detector_processor')
class MMWaveDetectorProcessor(Processor):
    def __init__(self):
        super().__init__()
        # Read configuration file
        self.Detector = Context.get_instance('MMWaveDetector')
        cfg = Context.get_parameter('MMWAVE_CONFIG')
        self.configPath = Context.get_file_path(cfg)
        with open(self.configPath, 'r') as fp:
            mmwaveConfigContent = fp.read()
        self.cfg = get_config(mmwaveConfigContent)

    def __call__(self, task: Task):
        data_file_path = task.get_file_path()
        fit = FrameIter(self.cfg, [data_file_path])
        framedata = next(iter(fit))
        result = self.infer(framedata)

        # Store results in task
        task.set_current_content(result)
        return task

    def infer(self, data):
        assert self.Detector, 'No mmw Detector defined!'

        with Timer(f'MMWave Detector'):
            process_output = self.Detector(data)

        return process_output


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


def count_ones(x):
    cnt = 0
    while (0 != x):
        if (x & 1) != 0:
            cnt = cnt + 1
        x = x >> 1
    return cnt


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
        # with open(setupJsonFileName, 'r') as f:
        #     setupJsonFileContent = f.read()
        with open(mmwaveJsonFileName, 'r') as f:
            mmwaveJsonFileContent = f.read()

        return self.from_jsons(mmwaveJsonFileContent)


# Get mmwave configuration and return
def get_config(mmwjsonContent: str) -> MMWaveConfig:
    return MMWaveConfig().from_jsons(mmwaveJsonFileContent=mmwjsonContent)


def calcFrameSize_2Byte(c: MMWaveConfig):
    # Complex IQ
    sz = c.calc_num_rx() * c.calc_num_tx() * c.numChirpPerFramePerTx * c.numSamplePerChirp * 2
    return sz * 2 if 1 == c.calc_num_rx() else sz


class FrameIter:
    def __init__(self, c: MMWaveConfig, files: 'list[str]'):
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

        # print(f'file[{self.fileIdx}]: {self.files[self.fileIdx]}')

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
