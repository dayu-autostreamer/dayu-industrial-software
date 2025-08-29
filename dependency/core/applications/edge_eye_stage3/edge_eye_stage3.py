import time
import redis

import util_ixpe

from core.lib.common import LOGGER,EncodeOps, Context, SystemConstant
from core.lib.network import NodeInfo, PortInfo


class EdgeEyeStage3:
    def __init__(self):
        self.pool = redis.ConnectionPool(host=NodeInfo.hostname2ip(NodeInfo.get_cloud_node()),
                                         port=PortInfo.get_component_port(SystemConstant.REDIS.value),
                                         max_connections=10)
        self.redis = redis.Redis(connection_pool=self.pool)

        self.lps = 0
        self.rps = 0
        self.pos_calculator = util_ixpe.CalPosition()
        self.abnormal_detector = util_ixpe.AbnormalDetector(
            w1=5, w2=7, e=7, buffer_size=100)
        self.lastls = self.lps
        self.lastrs = self.rps
        self.first_done_flag = False

    def __call__(self, input_ctx, redis_address):
        start = time.time()
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

        end_pre = time.time()
        LOGGER.debug(f'preprocess time: {end_pre - start}s')

        try:

            output_ctx = self.process_task(input_ctx, redis_address)
        except Exception as e:
            output_ctx = {}

        end_process = time.time()
        LOGGER.debug(f'process time: {end_process - end_pre}s')

        if "frame" in output_ctx:
            output_ctx["frame"] = EncodeOps.encode_image(output_ctx["frame"])

        end_after = time.time()
        LOGGER.debug(f'after process time: {end_after - end_process}s')

        end = time.time()
        LOGGER.debug(f'real service call time: {end - start}s')

        return output_ctx

    def process_task(self, input_ctx, redis_address):
        output_ctx = {}

        if 'frame' not in input_ctx:
            return output_ctx

        frame = input_ctx['frame']

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
            # 因为roi size变大 2*h and 2*w 导致不能直接使用计算出来的单位xxx
            lroi, rroi, labs_point, rabs_point, frame = input_ctx["srl"], input_ctx["srr"], input_ctx[
                "labs_point"], input_ctx["rabs_point"], input_ctx['frame']
            # print(type(lroi))
            # print(type(rroi))
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
        self.set_edge_position(int(self.lps), int(self.rps), redis_address)
        output_ctx["frame"] = frame
        output_ctx["lps"] = self.lps
        output_ctx["rps"] = self.rps
        return output_ctx

    def set_edge_position(self, lps, rps, redis_address):
        self.redis.set("lps", str(lps))
        self.redis.set("rps", str(rps))
        http_request(url=redis_address, method='POST', json={'lps': lps, 'rps': rps})
