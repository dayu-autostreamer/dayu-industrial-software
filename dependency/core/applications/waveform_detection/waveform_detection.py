from typing import List

import numpy as np
import cv2
import os
from core.lib.common import LOGGER

DEBUG_PRINT = False


class WaveformDetection:
    def __init__(self):
        pass

    def is_multi_row_straight_line(self, defect_rows, pixel_threshold=8, low_pixel_ratio_threshold=0.5):
        """
        检测多行缺陷是否形成斜线（基于像素数量阈值）
        
        参数:
        - defect_rows: 缺陷行信息列表，每个元素包含row, defect_pixels, min_col, max_col
        - pixel_threshold: 每行缺陷像素数量阈值
        
        返回:
        - True: 是斜线，应该排除
        - False: 不是斜线，可能是真正的缺陷
        """
        # 按行号排序
        defect_rows.sort(key=lambda x: x['row'])
        
        # 检查每行的缺陷像素数量
        low_pixel_count_rows = 0
        total_rows = len(defect_rows)
        
        for defect_row in defect_rows:
            pixel_count = len(defect_row['defect_pixels'])
            if pixel_count < pixel_threshold:
                low_pixel_count_rows += 1
        
        # 计算低像素数量行的比例
        low_pixel_ratio = low_pixel_count_rows / total_rows
        if DEBUG_PRINT:
            print(f"低像素数量行比例: {low_pixel_ratio:.2f} ({low_pixel_count_rows}/{total_rows})")
        
        # 如果大部分行的缺陷像素数量都低于阈值，认为是斜线
        if low_pixel_ratio > low_pixel_ratio_threshold:  # 70%以上的行都低于阈值
            return True
        
        return False

    def detect_red_lines(self, image):
        """
        检测图像中的红色虚线
        返回每个下半部分区域的红色线条坐标（写死位置）
        """
        height, width = image.shape[:2]
        
        if DEBUG_PRINT:
            print(f"\n图像尺寸: {width}x{height}")
        
        # 根据手动测量的坐标数据写死红色线条位置
        # 原始1920宽度图片的坐标：
        # 区域0: 220, 270
        # 区域1: 700, 750  
        # 区域2: 1180, 1230
        # 区域3: 1660, 1710
        
        # 计算归一化比例
        scale_factor = width / 1920.0
        
        # 写死红色线条位置（归一化到当前图像宽度）
        red_lines_by_region = []
        
        # 每个区域的红色线条绝对坐标（基于1920宽度）
        absolute_red_lines = [
            [220, 270],   # 区域0
            [700, 750],   # 区域1
            [1180, 1230], # 区域2
            [1660, 1710]  # 区域3
        ]
        
        for region_idx in range(4):
            # 获取该区域的红色线条坐标
            region_red_lines_abs = absolute_red_lines[region_idx]
            
            # 归一化到当前图像宽度
            region_red_lines = [x * scale_factor for x in region_red_lines_abs]
            
            if DEBUG_PRINT:
                print(f"--- 区域 {region_idx} ---")
                print(f"  原始坐标(1920宽度): {region_red_lines_abs}")
                print(f"  归一化坐标({width}宽度): {[f'{x:.1f}' for x in region_red_lines]}")
            
            red_lines_by_region.append(region_red_lines)
        
        if DEBUG_PRINT:
            print(f"\n=== 红色线条检测完成 ===")
            for i, lines in enumerate(red_lines_by_region):
                print(f"区域{i}: {[f'{x:.1f}' for x in lines]}")
        
        return red_lines_by_region

    def analyze_defect_pattern_by_rows(self, image, red_lines_by_region, duration=4):
        """
        使用向量化逐行扫描分析缺陷模式（加速版）
        """
        height, width = image.shape[:2]
        lower_half = image[height//2:, :]
        lower_height = height // 2

        if DEBUG_PRINT:
            print(f"\n=== 逐行缺陷分析日志（向量化） ===")
            print(f"下半部分尺寸: {width}x{lower_height}")
            print(f"最小持续行数: {duration}")

        total_defect_segments = []

        for region_idx in range(4):
            if DEBUG_PRINT:
                print(f"\n--- 区域 {region_idx} 逐行分析 ---")

            # 红色线条
            red_left, red_right = red_lines_by_region[region_idx]

            # 区域边界
            region_width = width // 4
            region_start_x = region_idx * region_width
            region_end_x = (region_idx + 1) * region_width
            effective_width = region_width * 0.6
            effective_start_x = int(region_start_x + (region_width - effective_width) // 2)
            effective_end_x = int(effective_start_x + effective_width)

            # 纵向有效区域
            effective_height = int(lower_height * 0.6)
            effective_start_row = int((lower_height - effective_height) // 2)
            effective_end_row = effective_start_row + effective_height

            # 提取有效区域
            region_area = lower_half[effective_start_row:effective_end_row, effective_start_x:effective_end_x]

            # 向量化黑色像素检测
            black_mask = np.all(region_area < 50, axis=2)  # True表示黑色像素

            # 列索引向量化
            col_indices = np.arange(effective_start_x, effective_end_x)
            # 构建列越界掩码
            left_mask = col_indices < red_left
            right_mask = col_indices > red_right
            col_out_of_red_mask = left_mask | right_mask  # 超出红线范围的列
            col_out_of_red_mask = np.tile(col_out_of_red_mask, (effective_height, 1))  # 扩展到行

            # 最终缺陷掩码
            defect_mask = black_mask & col_out_of_red_mask

            # 每行缺陷像素位置
            defect_rows = []
            current_defect_start = None
            current_defect_end = None
            all_defect_rows = []

            for row_idx, row_defects in enumerate(defect_mask):
                defect_pixels = np.where(row_defects)[0] + effective_start_x  # 列位置映射回原图
                if defect_pixels.size > 0:
                    all_defect_rows.append({
                        'row': row_idx,
                        'defect_pixels': defect_pixels.tolist(),
                        'min_col': defect_pixels.min(),
                        'max_col': defect_pixels.max()
                    })
                    if current_defect_start is None:
                        current_defect_start = row_idx
                    current_defect_end = row_idx
                else:
                    if current_defect_start is not None:
                        defect_duration = current_defect_end - current_defect_start + 1
                        if defect_duration > duration:
                            segment_defect_rows = [d for d in all_defect_rows if current_defect_start <= d['row'] <= current_defect_end]
                            if not self.is_multi_row_straight_line(segment_defect_rows):
                                defect_rows.append({
                                    'start_row': current_defect_start,
                                    'end_row': current_defect_end,
                                    'duration': defect_duration,
                                    'region_idx': region_idx
                                })
                        current_defect_start = None
                        current_defect_end = None

            total_defect_segments.extend(defect_rows)

        if total_defect_segments:
            return True, f"检测到{len(total_defect_segments)}个缺陷行段", total_defect_segments
        else:
            return False, "未检测到缺陷", []
        
        
    def get_defect_detections(self, image, defect_segments):
        """生成缺陷检测框信息（仿YOLO格式）"""
        height, width = image.shape[:2]
        lower_half_start = height // 2

        result_boxes = []
        result_scores = []
        result_class_id = []

        for defect in defect_segments:
            region_idx = defect['region_idx']
            start_row = defect['start_row']
            end_row = defect['end_row']

            # 计算区域边界
            region_width = width // 4
            region_start_x = region_idx * region_width
            region_end_x = (region_idx + 1) * region_width

            # 有效区域计算
            effective_width = region_width * 0.6
            effective_start_x = int(region_start_x + (region_width - effective_width) // 2)
            effective_end_x = int(effective_start_x + effective_width)

            # 纵向有效区域偏移
            effective_height = int((height // 2) * 0.6)
            effective_start_row = int(((height // 2) - effective_height) // 2)

            # 修正Y坐标（加上下半部分和纵向有效区域偏移）
            start_y = lower_half_start + effective_start_row + start_row
            end_y = lower_half_start + effective_start_row + end_row

            # 添加检测结果
            result_boxes.append([effective_start_x, start_y, effective_end_x, end_y])
            result_scores.append(1.0)
            result_class_id.append(0)

        return result_boxes, result_scores, result_class_id


    def infer(self, image):
        """单图推理接口"""
        duration = 4
        red_lines_by_region = self.detect_red_lines(image)
        has_defect, message, defect_segments = self.analyze_defect_pattern_by_rows(
            image, red_lines_by_region, duration
        )
        
        # 生成检测框
        result_boxes, result_scores, result_class_id = self.get_defect_detections(
            image, defect_segments
        )
        
        return result_boxes, result_scores, result_class_id

    def __call__(self, images: List[np.ndarray]):
        """批量推理接口"""
        return [self.infer(image) for image in images]