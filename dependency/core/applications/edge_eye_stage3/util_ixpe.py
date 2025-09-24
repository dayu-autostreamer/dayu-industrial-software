import numpy as np
import cv2 as cv


def edgeDetection(frame, accuray='normal', operator='canny', ff=None):
    if ff is None:
        ff = {
            'ksize': (3, 3),
            'sigmaX': 0,
            'lThreshold': 50,
            'hThreshold': 150,
            'vl': 30,
            'hl': 30,
            'theta': 0.436,
            'apertureSize': 3,
            'L2gradient': False
        }
        if accuray == 'low':
            ff['lThreshold'] = 70
            ff['hThreshold'] = 210
            ff['apertureSize'] = 5
        elif accuray == 'high':
            ff['lThreshold'] = 20
            ff['hThreshold'] = 60
            ff['apertureSize'] = 7
            ff['L2gradient'] = True
    gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
    # grayGaussian = gray
    grayGaussian = cv.GaussianBlur(gray, ff['ksize'], ff['sigmaX'])
    if operator == 'canny':
        edges = cv.Canny(grayGaussian, ff['lThreshold'], ff['hThreshold'],
                         apertureSize=ff['apertureSize'], L2gradient=ff['L2gradient'])
    elif operator == 'sobel':
        img_sobel_x = cv.Sobel(grayGaussian, cv.CV_64F, 1, 0, ksize=3)
        img_sobel_y = cv.Sobel(grayGaussian, cv.CV_64F, 0, 1, ksize=3)
        img_sobel_x = cv.convertScaleAbs(img_sobel_x)
        img_sobel_y = cv.convertScaleAbs(img_sobel_y)
        edges = cv.addWeighted(img_sobel_x, 0.5, img_sobel_y, 0.5, 0)
    elif operator == 'laplace':
        gray_lap = cv.Laplacian(grayGaussian, cv.CV_16S, ksize=3)
        edges = cv.convertScaleAbs(gray_lap)
    elif operator == 'scharr':
        img_scharr_x = cv.Scharr(grayGaussian, cv.CV_64F, 1, 0)
        img_scharr_y = cv.Scharr(grayGaussian, cv.CV_64F, 0, 1)
        img_scharr_x = cv.convertScaleAbs(img_scharr_x)
        img_scharr_y = cv.convertScaleAbs(img_scharr_y)
        edges = cv.addWeighted(img_scharr_x, 0.5, img_scharr_y, 0.5, 0)
    # lines = cv.HoughLines(edges, 1, np.pi/180, 25)
    # lines1 = cv.HoughLines(
    #     edges, 1, np.pi/180, ff.hl_threshold, min_theta=0, max_theta=ff.t_threshold)  # 考虑更换为概率霍夫变换？？
    # lines2 = cv.HoughLines(edges, 1, np.pi/180, ff.hl_threshold,
    #                         min_theta=(np.pi-ff.t_threshold), max_theta=np.pi)
    else:
        raise ValueError('Operator must be one of "canny", "sobel", "laplace", "scharr"')
    return edges


class CalPosition:
    def __init__(self) -> None:
        self.ff = {
            'initial': False,
            'ksize': (3, 3),
            'sigmaX': 0,
            'lThreshold': 60,
            'hThreshold': 150,
            'vl': 30,
            'hl': 30,
            'theta': 0.436,
            'apertureSize': 3,
            'L2gradient': False
        }
        self.commom_points = []
        self.sta_points = []
        self.mov_points = []
        self.extract_counter = 0
        # 先把阈值的数值设定搞完。。。

        self.vertical_threshold = {'rho': 25, 'theta': np.pi / 180 * 30}  # 360: 0-30, 150-180
        self.horizontal_threshold = {'rho': 25, 'theta': np.pi / 180 * 15}  # 360: 75-105
        self.le_last = 0
        self.ri_last = 0
        self.centerLine = 30
        self.abs_point = (0, 0)

    def extractCommomPoints(self, edges):
        if self.extract_counter == 0:
            self.commom_points = edges
        elif self.extract_counter < 20:
            self.commom_points &= edges
        else:
            if self.extract_counter > 100:  # 随便操作下防止溢出
                self.extract_counter = 19
        self.extract_counter += 1
        return self.extract_counter

    def generateDoubleThreshold(self, frame):
        if self.ff['initial']:
            pass
        else:
            performance = False
            while True:
                lThreshold = self.ff['lThreshold']
                hThreshold = self.ff['hThreshold']

                if frame is None:
                    raise ValueError("frame is None")
                if frame.size == 0:
                    raise ValueError("frame is empty")
                if frame.dtype not in [np.uint8, np.uint16, np.float32]:
                    raise ValueError(f"frame has an invalid data type: {frame.dtype}")

                gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
                edges = cv.Canny(gray, lThreshold, hThreshold)
                # this performance is really important !!
                # vertical boundary and horizontal reference bar should all in consideration !!
                performance = self.evaPerformance(edges)
                if performance:
                    self.ff['initial'] = performance
                    lThreshold = self.ff['lThreshold']
                    hThreshold = self.ff['hThreshold']
                    break
                else:
                    if lThreshold >= 35:
                        lThreshold -= 10
                    if hThreshold >= 105:
                        hThreshold -= 20
        return self.ff

    # 有机会的话 把各处的图像都imshow出来，方便操作xxx观察下到底是哪一步出了问题xx
    def evaPerformance(self, edges):
        vPerformance = False
        hPerformance = False
        vl = self.ff['vl']
        lines = cv.HoughLines(edges, 1, np.pi / 180, vl)
        theta_threshold = np.pi / 6
        height, width = edges.shape[:2]
        boundry = width // 2
        max_material_width = width // 5 * 4
        if lines is not None:
            lLine = []
            rLine = []
            hRhoCount = []
            for line in lines:
                rho, theta = line[0]
                # horizontal line detection 75~105
                if theta >= np.pi / 180 * 75 and theta <= np.pi / 180 * 105:
                    hRhoCount.append(rho)
                # vertical line detection
                if (rho > 0 and theta < theta_threshold) or (rho < 0 and np.pi - theta < theta_threshold):
                    if abs(rho) > boundry:
                        rLine.append(abs(rho))
                    else:
                        lLine.append(abs(rho))
            if min(rLine) - max(lLine) < max_material_width:
                vPerformance = True
            hRhoCount.sort()
            topline = np.sum(1 for num in hRhoCount if num < (hRhoCount[0] + hRhoCount[-1]) / 2)
            bottomline = np.sum(1 for num in hRhoCount if num > (hRhoCount[0] + hRhoCount[-1]) / 2)
            if topline > 4 or bottomline > 4:
                hPerformance = True

        return vPerformance and hPerformance

    def calculatePosInBarROI(self, bar_roi, abs_point):
        self.abs_point = abs_point
        ff = self.generateDoubleThreshold(bar_roi)
        edges = edgeDetection(bar_roi, ff=ff)

        # showFrame(edges,'original_edges')
        counter = self.extractCommomPoints(edges)
        if counter < 20:
            return 0, 0
        self.sta_points = edges & self.commom_points
        self.mov_points = edges - self.sta_points
        # showFrame(self.commom_points,'common_points')
        # showFrame(self.sta_points,'sta_points')
        # showFrame(self.mov_points,'mov_points')
        boundry_line = self.calculateBoundry(self.mov_points)
        lsp, rsp = self.sta_points[...,
        :boundry_line], self.sta_points[..., boundry_line + 1:]
        lmp, rmp = self.mov_points[...,
        :boundry_line], self.mov_points[..., boundry_line + 1:]
        le, re = edges[..., :boundry_line], edges[..., boundry_line + 1:]
        lps = self.biDirectionTracking(
            le, lsp, lmp, self.commom_points[..., : boundry_line], pos='left')
        rps = self.biDirectionTracking(
            re, rsp, rmp, self.commom_points[..., boundry_line + 1:], pos='right')
        return lps, rps + boundry_line

    def calculateBoundry(self, mov_points):
        height, width = mov_points.shape[:2]
        boundry = width // 2
        # further improvement by distance separation
        return boundry

    def calculatePosInMROI(self, mroi, position='left', abs_point=(0, 0)):
        lps = 0
        rps = 0
        ff = self.ff
        # 这里的edges只是一块区域，最好附加上相对于bar_roi的详细位置
        super_edges = edgeDetection(mroi, ff=ff)
        # showFrame(super_edges, 'sr_edges_' + position)
        edges = cv.resize(super_edges, None, fx=0.5, fy=0.5, interpolation=cv.INTER_AREA)
        # showFrame(edges, 'lr_edges_' + position)
        relative_px = abs_point[0] - self.abs_point[0]
        relative_py = abs_point[1] - self.abs_point[1]
        # logger.info("relative_px = %s, relative_py = %s" % (relative_px, relative_py))
        width, height = edges.shape[:2]
        # logger.info("edge_width = %s, edge_height = %s" % (width, height))
        # logger.info("common_points_shape = (%s, %s)" % np.array(self.commom_points).shape)

        # print("relative_px = %s, relative_py = %s" % (relative_px, relative_py))
        # print("edge_width = %s, edge_height = %s" % (width, height))
        # print(self.commom_points)
        common_points = self.commom_points[relative_py:(relative_py + width), relative_px:(relative_px + height)]  # xxx
        # showFrame(common_points, 'common_points')
        # further improvement by set local points
        self.sta_points = edges & common_points
        self.mov_points = edges - self.sta_points
        # showFrame(self.sta_points, 'sta_points')
        # showFrame(self.mov_points, 'mov_points')
        # logger.info("sta_points_len = %s, mov_points_len = %s" % (len(self.sta_points), len(self.mov_points)))
        if position == 'left':
            lps = self.biDirectionTracking(
                edges, self.sta_points, self.mov_points, common_points, position)
            return lps
        elif position == 'right':
            rps = self.biDirectionTracking(
                edges, self.sta_points, self.mov_points, common_points, position)
            return rps
        else:
            return -1

    def complimentaryFilter(self, vl, hl, last):
        if vl < 0 and hl < 0:
            return last
        elif vl < 0:
            return hl
        elif hl < 0:
            return vl
        dis = abs(vl - last) + abs(hl - last)
        if dis == 0:
            return vl
        cur = abs(vl - last) * hl + abs(hl - last) * vl
        cur = cur / dis
        return cur

    def calAxisPoints(self, line, x=None, y=None):
        ''' houghlines 直线的计算需要特别注意才行，特殊的定义
        目前来看这里的计算很可能出现了点问题xxx
        '''
        rho, theta = line
        if x is not None:
            y = rho - x * np.cos(theta)
            if np.sin(theta) == 0:
                y = 0
            else:
                y = y / np.sin(theta)
            return y
        if y is not None:
            x = rho - y * np.sin(theta)
            if np.cos(theta) == 0:
                x = 0
            else:
                x = x / np.cos(theta)
            return x

    def biDirectionTracking(self, edges, sta, mov, common_points, pos='left'):  # 问题在这里面
        # showFrame(edges, 'bi-edges-%s' % pos)
        lines = cv.HoughLines(
            edges, 1, np.pi / 180, self.vertical_threshold['rho'])
        vTrack = []
        if lines is not None:
            for line in lines:
                rho, theta = line[0]
                theta_threshold = self.vertical_threshold['theta']
                if (rho > 0 and theta < theta_threshold) or (rho < 0 and np.pi - theta < theta_threshold):
                    vTrack.append([rho, theta])
        vl = -1  # init value for vertical line tracking result (x value)
        if len(vTrack) > 0:
            vlRes = []
            for li in vTrack:
                vlRes.append(self.calAxisPoints(li, y=self.centerLine))
            vl = np.average(vlRes)
        hlines = cv.HoughLinesP(edges, 1, np.pi / 180, self.horizontal_threshold['rho'], minLineLength=20,
                                maxLineGap=10)
        hTrack = []
        if hlines is not None:
            for line in hlines:
                x1, y1, x2, y2 = line[0]
                if pos == 'left':
                    hTrack.append(max(x1, x2))
                else:
                    hTrack.append(min(x1, x2))
        hl = -1  # init value for horizontal line tracking result (x value)
        if len(hTrack) > 0:
            if pos == 'left':
                hl = max(hTrack)
            else:
                hl = min(hTrack)
        position = 0
        if pos == 'left':
            position = self.complimentaryFilter(vl, hl, self.le_last)  # 似乎是vl和hl求得不好
            lpx_log = '%s-%s-%s' % (vl, hl, position)
            # logger1.info('lpx log : ' + lpx_log)
            self.le_last = position
        elif pos == 'right':
            position = self.complimentaryFilter(vl, hl, self.ri_last)
            rpx_log = '%s-%s-%s' % (vl, hl, position)
            # logger2.info('rpx log : ' + rpx_log)
            self.ri_last = position
        return position

    def biDirectionTracking_bak(self, edges, sta, mov, common_points, pos='left'):
        '''实际运行之中还是太敏感了/common的提取效果没有想象之中的那么好--水平追踪时，边缘点经常发生变换
        整体的edges提取效果还可以
        '''
        # showFrame(edges, 'bi-edges-%s' % pos)
        # showFrame(sta, 'bi-sta-%s' % pos)
        # showFrame(mov, 'bi-mov-%s' % pos)
        # showFrame(common_points, 'bi-common_points-%s' % pos)
        lps = 0
        rps = 0
        vTrack = []
        hTrack = []
        lines = cv.HoughLines(
            mov, 1, np.pi / 180, self.vertical_threshold['rho'])
        if lines is None:
            lines = cv.HoughLines(edges, 1, np.pi / 180,
                                  self.vertical_threshold['rho'])
        if lines is not None:
            for line in lines:
                rho, theta = line[0]
                theta_threshold = self.vertical_threshold['theta']
                if (rho > 0 and theta < theta_threshold) or (rho < 0 and np.pi - theta < theta_threshold):
                    vTrack.append([rho, theta])
        # xxx
        hlines = cv.HoughLines(
            sta, 1, np.pi / 180, self.horizontal_threshold['rho'])
        if hlines is None:
            # operands could not be broadcast together with shapes (50,1050) (50,524)
            sta = common_points - common_points & edges
        vl = -1  # init value for vertical line tracking result (x value)
        if len(vTrack) > 0:
            vlRes = []
            for li in vTrack:
                vlRes.append(self.calAxisPoints(li, y=self.centerLine))
            vl = np.average(vlRes)
        hl = -1  # init value for horizontal line tracking result (x value)
        if len(hTrack) > 0:
            # xxx
            if pos == 'left':
                hl = np.max(sta[..., 1])  # find the centerest points in lsta
            elif pos == 'right':
                hl = np.min(sta[..., 1])  # same to hl
            else:
                hl = 0
        if pos == 'left':
            position = self.complimentaryFilter(vl, hl, self.le_last)
            self.le_last = position
        elif pos == 'right':
            position = self.complimentaryFilter(vl, hl, self.ri_last)
            self.ri_last = position
        else:
            position = 0
        return position


class AbnormalDetector:
    def __init__(self, w1, w2, e, buffer_size=100) -> None:
        self.threshold_w1 = w1
        self.threshold_w2 = w2
        self.threshold_e = e
        self.le_pos = []
        self.ri_pos = []
        self.material_width = []
        self.buffer_size = 100

    def repair(self, lpx, rpx):
        width = abs(rpx - lpx)
        if len(self.material_width) <= self.buffer_size // 10:
            pass
        else:
            d_lpx = abs(lpx - self.le_pos[-1])
            d_rpx = abs(rpx - self.ri_pos[-1])
            d_width = abs(self.material_width[-1] - width)
            if d_width <= self.threshold_w1 or (d_lpx <= self.threshold_e and d_rpx <= self.threshold_e):
                pass
            elif d_lpx > 2 * self.threshold_e or d_rpx > 2 * self.threshold_e:
                if d_lpx > 2 * self.threshold_e:
                    lpx = self.threshold_e
                if d_rpx > 2 * self.threshold_e:
                    rpx = self.threshold_e
            elif self.threshold_w1 < d_width < self.threshold_w2:
                if self.threshold_e < d_lpx < 2 * self.threshold_e:
                    lpx = 0.9 * self.threshold_e + 0.1 * lpx
                if self.threshold_e < d_rpx < 2 * self.threshold_e:
                    rpx = 0.9 * self.threshold_e + 0.1 * rpx
            else:
                if self.threshold_e < d_lpx < 2 * self.threshold_e:
                    lpx = 0.99 * self.threshold_e + 0.01 * lpx
                if self.threshold_e < d_rpx < 2 * self.threshold_e:
                    rpx = 0.99 * self.threshold_e + 0.01 * rpx
        self.le_pos.append(lpx)
        self.ri_pos.append(rpx)
        self.material_width.append(width)
        if len(self.material_width) > self.buffer_size:
            self.le_pos.pop(0)
            self.ri_pos.pop(0)
            self.material_width.pop(0)

        return self.le_pos[-1], self.ri_pos[-1]
