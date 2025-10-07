import numpy as np
from .mmwave_config import MMWaveConfig


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


def calcFrameSize_2Byte(c: MMWaveConfig):
    # Complex IQ
    sz = c.calc_num_rx() * c.calc_num_tx() * c.numChirpPerFramePerTx * c.numSamplePerChirp * 2
    return sz * 2 if 1 == c.calc_num_rx() else sz
