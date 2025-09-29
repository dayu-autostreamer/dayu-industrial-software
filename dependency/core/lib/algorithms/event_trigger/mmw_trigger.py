import abc
import os
import cv2
import numpy as np
from core.lib.common import ClassFactory, ClassType, EncodeOps, LOGGER
from core.lib.content import Task
from .base_trigger import BaseTrigger

__all__ = ('MmwTrigger',)


@ClassFactory.register(ClassType.EVENT_TRIGGER, alias='mmw')
class MmwTrigger(BaseTrigger, abc.ABC):
    frame_history = []
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.window_num = 5
        self.window_len = 30
        self.threshold = 0.2

    def __call__(self, task: Task):
        from matplotlib import pyplot as plt
        single_res = task.get_dag().get_node('mmw-detection').service.get_content_data()
        MmwTrigger.frame_history.append(single_res)
        if len(MmwTrigger.frame_history) >= 3*self.window_len*self.window_num:
            MmwTrigger.frame_history = MmwTrigger.frame_history[-self.window_len * self.window_num:]
        cnt = 0
        if len(MmwTrigger.frame_history) < self.window_len * self.window_num:
            return False, {}
        for i in range(self.window_num):
            frame_window = MmwTrigger.frame_history[-(i+1)*self.window_len:-i*self.window_len]
            if i == 0:
                frame_window = MmwTrigger.frame_history[-(i+1)*self.window_len:]
            if np.var(frame_window) > self.threshold:
                cnt += 1
        if cnt >= (self.window_num+1)/2:
            # 把最近窗口的波形画出来
            # 中文乱码解决方法
            plt.rcParams['font.family'] = ['Arial Unicode MS', 'Microsoft YaHei', 'SimHei', 'sans-serif']
            plt.rcParams['axes.unicode_minus'] = False

            # 设置全局字体大小
            plt.rcParams['font.size'] = 20  # 基础字体大小
            plt.rcParams['axes.titlesize'] = 24  # 标题字体大小
            plt.rcParams['axes.labelsize'] = 22  # 坐标轴标签字体大小
            plt.rcParams['xtick.labelsize'] = 18  # x轴刻度字体大小
            plt.rcParams['ytick.labelsize'] = 18  # y轴刻度字体大小
            plt.rcParams['legend.fontsize'] = 20  # 图例字体大小

            plt.figure(figsize=(36, 18), dpi=200)
            # plt.ylim([-10, 10])

            # 绘制数据，可以适当增加线宽使图形更清晰
            plt.plot(np.asarray(MmwTrigger.frame_history[-self.window_len * self.window_num:]),
                     linewidth=2)  # 增加线宽

            plt.legend()
            plt.title('最近时间窗口的波形图', fontsize=28)  # 可以单独设置更大的标题字体
            plt.xlabel('最近任务下标', fontsize=24)  # 单独设置x轴标签字体
            plt.ylabel('幅值', fontsize=24)  # 添加y轴标签并设置字体大小

            # 可选：设置坐标轴刻度密度（如果刻度太密可以调整）
            plt.tight_layout()

            # 保存图片
            plt.savefig('mmw.png', bbox_inches='tight', dpi=200)  # bbox_inches='tight' 确保保存时不会裁剪内容
            plt.close()

            image = cv2.imread('mmw.png')
            os.remove(os.path.abspath('mmw.png'))
            try:
                base64_data = EncodeOps.encode_image(image)
            except Exception as e:
                LOGGER.warning(f'image file!!!')
                return True, {}

            return True, {'image': base64_data}
        else:
            return False, {}
