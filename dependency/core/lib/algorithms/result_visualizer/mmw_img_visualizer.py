import abc
import numpy as np
from core.lib.common import ClassFactory, ClassType,EncodeOps, LOGGER
from core.lib.content import Task
from scipy.signal import savgol_filter
import cv2

from .image_visualizer import ImageVisualizer

__all__ = ('MMWImageVisualizer',)


@ClassFactory.register(ClassType.RESULT_VISUALIZER, alias='mmw_image')
class MMWImageVisualizer(ImageVisualizer, abc.ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.frame_results = []
        import matplotlib
        # Ensure non-interactive backend to avoid GUI overhead
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
        try:
            plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
            plt.rcParams['axes.unicode_minus'] = False
        except Exception:
            pass
            # 设置字体大小
        plt.rcParams['font.size'] = 14
        plt.rcParams['axes.titlesize'] = 16
        plt.rcParams['axes.labelsize'] = 14
        plt.rcParams['xtick.labelsize'] = 12
        plt.rcParams['ytick.labelsize'] = 12
        plt.rcParams['legend.fontsize'] = 12

        # 存储参数
        self.window = 51
        self.poly = 3
        self.roll_std_window = 101
        self.k_sigma = 3
        # 创建图形和画布
        self.fig = plt.figure(figsize=(12, 5), dpi=200)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)

        # 创建空的图形元素
        self.line_raw, = self.ax.plot([], [], label='raw', alpha=0.4)
        self.line_smooth, = self.ax.plot([], [], label='smoothed', linewidth=2)
        self.line_mean, = self.ax.plot([], [], label='rolling mean', linestyle='--', linewidth=1)
        self.fill_between = None
        self.scatter_anomalies = None

        self.ax.set_title('结果总览', fontsize=18)
        self.ax.set_xlabel('任务下标')
        self.ax.set_ylabel('结果')
        # 添加网格和图例
        self.ax.grid(alpha=0.2)
        self.ax.legend()

        # 初始化图像缓冲区
        self.canvas.draw()
        w, h = self.canvas.get_width_height()
        self._img = np.empty((h, w, 3), dtype=np.uint8)
    def plot(self):
        x = np.arange(len(self.frame_results))
        y = np.asarray(self.frame_results)
        # 处理数据长度不足的情况
        if len(y) <= 1:
            # 如果只有一个数据点，直接绘制点
            self.line_raw.set_data(x, y)
            self.line_smooth.set_data(x, y)
            self.line_mean.set_data(x, y)

            # 清除填充和异常点
            if self.fill_between:
                self.fill_between.remove()
                self.fill_between = None
            if self.scatter_anomalies:
                self.scatter_anomalies.remove()
                self.scatter_anomalies = None

            # 设置坐标轴范围
            if len(y) == 1:
                self.ax.set_xlim(-0.5, 0.5)
                self.ax.set_ylim(y[0] - 1, y[0] + 1)
            else:
                self.ax.set_xlim(0, max(1, len(y) - 1))
                self.ax.set_ylim(np.min(y) - 1, np.max(y) + 1)
        else:
            # 平滑: Savitzky-Golay (保留峰形)
            if len(y) >= self.window:
                y_smooth = savgol_filter(y, window_length=self.window, polyorder=self.poly)
            else:
                # 如果数据长度小于窗口，使用较小的窗口
                if len(y) >= 5:
                    window_adj = len(y) if len(y) % 2 == 1 else len(y) - 1
                    poly_adj = min(self.poly, window_adj - 1)
                    y_smooth = savgol_filter(y, window_length=window_adj, polyorder=poly_adj)
                else:
                    y_smooth = y.copy()

            # 滚动标准差和均值 (处理边界)
            if len(y) >= self.roll_std_window:
                std_roll = np.sqrt(np.convolve((y - np.mean(y)) ** 2,
                                               np.ones(self.roll_std_window) / self.roll_std_window,
                                               mode='same'))
                mean_roll = np.convolve(y, np.ones(self.roll_std_window) / self.roll_std_window, mode='same')
            else:
                # 如果数据长度小于窗口，使用全局统计
                std_roll = np.full_like(y, np.std(y))
                mean_roll = np.full_like(y, np.mean(y))

            upper = mean_roll + self.k_sigma * std_roll
            lower = mean_roll - self.k_sigma * std_roll

            anomalies = np.where((y > upper) | (y < lower))[0]

            # 更新图形元素
            self.line_raw.set_data(x, y)
            self.line_smooth.set_data(x, y_smooth)
            self.line_mean.set_data(x, mean_roll)

            # 更新填充区域
            if self.fill_between:
                self.fill_between.remove()
            self.fill_between = self.ax.fill_between(x, lower, upper, color='orange', alpha=0.15,
                                                     label=f'±{self.k_sigma}σ (rolling)')

            # 更新异常点
            if self.scatter_anomalies:
                self.scatter_anomalies.remove()
            if anomalies.size:
                self.scatter_anomalies = self.ax.scatter(anomalies, y[anomalies], color='red', s=20, label='anomalies')
            else:
                self.scatter_anomalies = None

            # 更新图例
            handles, labels = self.ax.get_legend_handles_labels()
            if self.fill_between:
                handles.append(self.fill_between)
                labels.append(f'±{self.k_sigma}σ (rolling)')
            if self.scatter_anomalies and anomalies.size:
                handles.append(self.scatter_anomalies)
                labels.append('anomalies')
            self.ax.legend(handles, labels)

            # 设置坐标轴范围
            self.ax.set_xlim(0, len(y) - 1)
            y_min = min(np.min(y), np.min(lower))
            y_max = max(np.max(y), np.max(upper))
            y_range = y_max - y_min
            self.ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)

        # 调整布局
        self.fig.tight_layout()

        # 重绘画布
        self.canvas.draw()

        # 更新图像缓冲区
        buf = np.frombuffer(self.canvas.tostring_rgb(), dtype=np.uint8)
        h, w, _ = self._img.shape
        np.copyto(self._img.reshape(-1), buf[:h * w * 3])
        # 返回BGR格式的图像（OpenCV常用格式）
        return self._img.copy()[..., ::-1]

    def __call__(self, task: Task):
        single_res =  task.get_dag().get_node('mmw-detection').service.get_content_data()
        self.frame_results.append(single_res)
        try:
            image = self.plot()
            base64_data = EncodeOps.encode_image(image)
        except Exception as e:
            base64_data = EncodeOps.encode_image(
                cv2.imread(self.default_visualization_image)
            )
            LOGGER.warning(f'Video visualization fetch failed: {str(e)}')
            LOGGER.exception(e)
        return {self.variables[0]: base64_data}
