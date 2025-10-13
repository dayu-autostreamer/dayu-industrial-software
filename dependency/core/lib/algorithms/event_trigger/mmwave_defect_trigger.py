import abc
import os
import cv2
import numpy as np
from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER
from core.lib.content import Task
from .base_trigger import BaseTrigger

__all__ = ('MMWaveDefectTrigger',)


@ClassFactory.register(ClassType.EVENT_TRIGGER, alias='mmwave_defect')
class MMWaveDefectTrigger(BaseTrigger, abc.ABC):
    frame_history = []
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.window_num = 5
        self.window_len = 30
        self.threshold = 0.2
        import matplotlib
        # Ensure non-interactive backend to avoid GUI overhead
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        try:
            plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
            plt.rcParams['axes.unicode_minus'] = False
        except Exception:
            pass
        # 绘图初始化
        # 设置超大字体
        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
        plt.rcParams['font.size'] = 30
        plt.rcParams['axes.titlesize'] = 40
        plt.rcParams['axes.labelsize'] = 35
        plt.rcParams['xtick.labelsize'] = 25
        plt.rcParams['ytick.labelsize'] = 25
        plt.rcParams['legend.fontsize'] = 30
        # 创建图形和画布
        self.fig = plt.figure(figsize=(36, 18), dpi=200)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)

        # 创建空的线对象
        self.line, = self.ax.plot([], [], linewidth=4)
        self.ax.set_title('最近时间窗口的波形图', fontsize=50, pad=30)
        self.ax.set_xlabel('最近任务下标', fontsize=40)
        self.ax.set_ylabel('幅值', fontsize=40)
        # 添加网格
        self.ax.grid(True, alpha=0.3)

        # 初始化图像缓冲区
        self.canvas.draw()
        w, h = self.canvas.get_width_height()
        self._img = np.empty((h, w, 3), dtype=np.uint8)
    def plot(self,data):
        x_data = np.arange(len(data))
        self.line.set_data(x_data, data)
        y_min, y_max = np.min(data), np.max(data)
        y_range = y_max - y_min

        # 添加5%的边距
        if y_range > 0:
            pad = y_range * 0.05
            self.ax.set_ylim(y_min - pad, y_max + pad)
        else:
            # 如果数据范围为零，设置默认范围
            self.ax.set_ylim(y_min - 1, y_max + 1)

        # 设置x轴范围
        self.ax.set_xlim(0, len(data))

        # 重绘画布
        self.canvas.draw()

        # 更新图像缓冲区
        buf = np.frombuffer(self.canvas.tostring_rgb(), dtype=np.uint8)
        h, w, _ = self._img.shape
        np.copyto(self._img.reshape(-1), buf[:h * w * 3])

        # 返回BGR格式的图像（OpenCV常用格式）
        return self._img.copy()[..., ::-1]

    def __call__(self, task: Task):
        distance_results = [result['distance'] for result in task.get_last_content()]
        MMWaveDefectTrigger.frame_history.extend(distance_results)
        if len(MMWaveDefectTrigger.frame_history) >= 3*self.window_len*self.window_num:
            MMWaveDefectTrigger.frame_history = MMWaveDefectTrigger.frame_history[-self.window_len * self.window_num:]
        cnt = 0
        if len(MMWaveDefectTrigger.frame_history) < self.window_len * self.window_num:
            return False, {}
        for i in range(self.window_num):
            frame_window = MMWaveDefectTrigger.frame_history[-(i+1)*self.window_len:-i*self.window_len]
            if i == 0:
                frame_window = MMWaveDefectTrigger.frame_history[-(i+1)*self.window_len:]
            if np.var(frame_window) > self.threshold:
                cnt += 1
        if cnt >= (self.window_num+1)/2:
            image = self.plot(np.asarray(MMWaveDefectTrigger.frame_history[-self.window_len * self.window_num:]))
            try:
                base64_data = EncodeOps.encode_image(image)
            except Exception as e:
                LOGGER.warning(f'image file!!!')
                return True, {}

            return True, {'image': base64_data}
        else:
            return False, {}
