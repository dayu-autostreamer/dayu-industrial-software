import redis

from .util_ixpe import CalPosition, AbnormalDetector

from core.lib.common import LOGGER, EncodeOps, SystemConstant
from core.lib.network import NodeInfo, PortInfo


class EdgeEyeStage3:
    def __init__(self):
        self.pool = redis.ConnectionPool(host=NodeInfo.hostname2ip(NodeInfo.get_cloud_node()),
                                         port=PortInfo.get_component_port(SystemConstant.REDIS.value),
                                         max_connections=10)
        self.redis = redis.Redis(connection_pool=self.pool)

        self.lps = 0
        self.rps = 0
        self.pos_calculator = CalPosition()
        self.abnormal_detector = AbnormalDetector(
            w1=5, w2=7, e=7, buffer_size=100)
        self.lastls = self.lps
        self.lastrs = self.rps
        self.first_done_flag = False

    def __call__(self, input_ctx):
        if 'frame' in input_ctx:
            input_ctx['frame'] = EncodeOps.decode_image(input_ctx['frame'])
        if "bar_roi" in input_ctx:
            input_ctx["bar_roi"] = EncodeOps.decode_image(input_ctx["bar_roi"])
        if "abs_point" in input_ctx:
            input_ctx["abs_point"] = tuple(input_ctx["abs_point"])
        if "srl" in input_ctx:
            input_ctx["srl"] = EncodeOps.decode_image(input_ctx["srl"])
        if "srr" in input_ctx:
            input_ctx["srr"] = EncodeOps.decode_image(input_ctx["srr"])
        if "labs_point" in input_ctx:
            input_ctx["labs_point"] = tuple(input_ctx["labs_point"])
        if "rabs_point" in input_ctx:
            input_ctx["rabs_point"] = tuple(input_ctx["rabs_point"])

        try:

            output_ctx = self.process_task(input_ctx)
        except Exception as e:
            output_ctx = {}

        return output_ctx

    def process_task(self, input_ctx):
        output_ctx = {}

        if len(input_ctx) not in [3, 5]:
            return output_ctx

        if len(input_ctx) == 3:
            LOGGER.debug("get three parameters from input_ctx")
            bar_roi, abs_point, frame = input_ctx["bar_roi"], input_ctx["abs_point"], input_ctx["frame"]
            self.lps, self.rps = self.pos_calculator.calculatePosInBarROI(
                bar_roi=bar_roi, abs_point=abs_point)

            if self.lps != 0:
                self.lastls = self.lps
            else:
                self.lps = self.lastls

            if self.lps != 0:
                self.lps = int(self.lps + abs_point[0])

            if self.rps != 0:
                self.lastrs = self.rps
            else:
                self.rps = self.lastrs
            if self.rps != 0:
                self.rps = int(self.rps + abs_point[0])

        elif len(input_ctx) == 5:
            LOGGER.debug("get five parameters from input_ctx")
            if not self.first_done_flag:
                self.first_done_flag = True
                LOGGER.debug('start get SR frame from queue')
            # ROI size increases (2*h and 2*w), cannot use the calculated unit directly
            lroi, rroi, labs_point, rabs_point, frame = (input_ctx["srl"], input_ctx["srr"],
                                                         input_ctx["labs_point"], input_ctx["rabs_point"],
                                                         input_ctx['frame'])
            LOGGER.debug(f'{labs_point=}, {rabs_point=}')

            if len(lroi) == 1:
                self.lps = lroi
            else:
                self.lps = self.pos_calculator.calculatePosInMROI(
                    lroi, 'left', labs_point)  # func 2
                self.lps = int(self.lps + labs_point[0])
            if len(rroi) == 1:
                self.rps = rroi
            else:
                self.rps = self.pos_calculator.calculatePosInMROI(
                    rroi, 'right', rabs_point)
                self.rps = int(self.rps + rabs_point[0])

        # calculate edge positions
        # lps, rps = abnormal_detector.repair(lpx=lps, rpx=rps)  # func3
        # update lps, rps
        self.set_edge_position(int(self.lps), int(self.rps))
        output_ctx["lps"] = self.lps
        output_ctx["rps"] = self.rps
        return output_ctx

    def set_edge_position(self, lps, rps):
        # Set a 60-second TTL so stale values don't persist across restarts
        self.redis.set("lps", str(lps), ex=60)
        self.redis.set("rps", str(rps), ex=60)
