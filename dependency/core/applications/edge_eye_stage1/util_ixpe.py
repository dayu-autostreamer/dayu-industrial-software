from pathlib import Path
from scipy import stats
import numpy as np
import cv2 as cv


def imgEntropy(image):
    if image.ndim > 2:
        image = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    simplified_image = image // 16  # (0,255) - (0,16)
    prob = np.bincount(np.reshape(simplified_image, -1))
    entropy = stats.entropy(prob)
    return entropy


def sobel_xaxis(img):
    img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    img_sobel_x = cv.Sobel(img, cv.CV_64F, 1, 0, ksize=3)
    img_sobel_x = cv.convertScaleAbs(img_sobel_x)
    return img_sobel_x


class MaterialDetection:
    def __init__(self, detection_area, buffer_size) -> None:
        self.p1, self.p2 = detection_area
        self.buffer_size = buffer_size
        shape = (720, 1280, 3)
        bg_image_path = str(Path(__file__).with_name('Empty_background.png'))
        raw_background = cv.imread(bg_image_path)
        self.background = raw_background[self.p1[1]:self.p2[1], self.p1[0]:self.p2[0]]
        self.counter = 0
        self.threshold_update = 0.05
        self.threshold_material = 1.0
        self.isMaterial = False

    def detect(self, frame):
        """counter状态机，节省资源，false时每一帧都比对，true时跳帧比对，以及background动态更新"""
        if self.isMaterial:
            self.counter += 1
            if self.counter <= 10:
                return self.isMaterial
            else:
                self.counter = 0
        d_area = frame[self.p1[1]:self.p2[1], self.p1[0]:self.p2[0]]
        if len(self.background) == 0:
            self.background = d_area
            self.counter = 0
        else:
            self.counter += 1
            diff_img = cv.absdiff(self.background, d_area)
            entropy = imgEntropy(diff_img)
            if entropy > self.threshold_material:
                self.isMaterial = True
                self.counter = 0
            else:
                self.isMaterial = False
                if entropy < self.threshold_update and self.counter > 60:
                    self.background = d_area
                    self.counter = 0
        return self.isMaterial


class BarSelection:
    def __init__(self, bar_area, buffer_size=10) -> None:
        self.p1, self.p2, self.p3, self.p4 = bar_area
        self.abs_point = (0, 0)
        self.buffer_size = buffer_size
        self.top_value = []
        self.bottom_value = []

    def calScore(self, frame):
        height, width = frame.shape[:2]
        step = 5
        myList = [[0, 0, 0]] * (width // step)
        for i in range(0, width // step):
            sw = frame[:, i:i + step * 10]  # sw: sliding window
            line = np.max(sw, axis=1)
            myList[i] = [i, np.mean(line), np.std(line)]
        myList = np.array(myList)
        index1 = myList[:, 1].argmax()
        _, mu1, sigma1 = myList[index1]
        le_bound = max(0, index1 - step * 10)
        ri_bound = min(index1 + step * 10, width - 1)
        myList[le_bound:ri_bound] = [index1, 0, 0]
        index2 = myList[:, 1].argmax()
        _, mu2, sigma2 = myList[index2]
        score = mu1 + mu2 - abs(mu1 - mu2) - np.log((sigma1 + 1) * (sigma2 + 1))
        return score

    def select(self, frame):
        roi1 = frame[self.p1[1]:self.p2[1], self.p1[0]:self.p2[0]]
        roi2 = frame[self.p3[1]:self.p4[1], self.p3[0]:self.p4[0]]
        if self.abs_point == (0, 0):
            if len(self.top_value) < self.buffer_size and len(self.bottom_value) < self.buffer_size:
                # 这里的top和bottom是指bar的位置关系
                top_edges = sobel_xaxis(roi1)
                bottom_edges = sobel_xaxis(roi2)
                self.top_value.append(self.calScore(top_edges))
                self.bottom_value.append(self.calScore(bottom_edges))
            if len(self.top_value) >= self.buffer_size and len(self.bottom_value) >= self.buffer_size:
                s1 = np.mean(self.top_value)
                s2 = np.mean(self.bottom_value)
                if s1 >= s2:
                    self.abs_point = self.p1
                else:
                    self.abs_point = self.p3
        if self.abs_point == self.p1:
            return roi1, self.abs_point
        elif self.abs_point == self.p3:
            return roi2, self.abs_point
        else:
            return frame, self.abs_point
