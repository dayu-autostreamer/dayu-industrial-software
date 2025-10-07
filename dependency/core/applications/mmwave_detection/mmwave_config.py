import json
import numpy as np


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