from typing import List

import numpy as np
from core.lib.common import LOGGER

DEBUG_PRINT = False


class WaveformDetection:
    def __init__(self):
        pass

    def is_multi_row_straight_line(self,defect_rows, pixel_threshold=8, low_pixel_ratio_threshold=0.5):
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
        通过逐行扫描分析缺陷模式
        
        参数:
        - image: 原始图像
        - red_lines_by_region: 按区域分组的红色线条
        - duration: 最小持续行数
        """
        height, width = image.shape[:2]
        lower_half = image[height//2:, :]
        lower_height = height // 2
        
        if DEBUG_PRINT:
            print(f"\n=== 逐行缺陷分析日志 ===")
            print(f"下半部分尺寸: {width}x{lower_height}")
            print(f"最小持续行数: {duration}")
        
        total_defect_segments = []
        
        for region_idx in range(4):
            if DEBUG_PRINT:
                print(f"\n--- 区域 {region_idx} 逐行分析 ---")
            
            # 获取该区域的红色线条坐标
            red_lines = red_lines_by_region[region_idx]
            red_left = red_lines[0]
            red_right = red_lines[1]
        
            if DEBUG_PRINT:
                print(f"  红色线条范围: {red_left:.1f} - {red_right:.1f}")
            
            # 计算区域边界（取中心60%）
            region_width = width // 4
            region_start_x = region_idx * region_width
            region_end_x = (region_idx + 1) * region_width
            
            # 取中心60%作为有效区域
            effective_width = region_width * 0.6
            effective_start_x = region_start_x + (region_width - effective_width) // 2
            effective_end_x = effective_start_x + effective_width
            
            if DEBUG_PRINT:
                print(f"  区域边界: {region_start_x} - {region_end_x}")
                print(f"  有效区域: {effective_start_x:.1f} - {effective_end_x:.1f} (宽度: {effective_width:.1f})")
            
            # 计算纵向有效区域（取中心60%）
            effective_height = lower_height * 0.6
            effective_start_row = int((lower_height - effective_height) // 2)
            effective_end_row = effective_start_row + int(effective_height)
            
            if DEBUG_PRINT:
                print(f"  纵向有效区域: y={effective_start_row + height//2}-{effective_end_row + height//2} (高度: {effective_height:.1f})")
            
            # 逐行扫描（只在有效区域内）
            defect_rows = []
            current_defect_start = None
            current_defect_end = None
            
            # 存储所有缺陷行的信息，用于后续的斜线检测
            all_defect_rows = []
            
            for row in range(effective_start_row, effective_end_row):
                # 检查当前行是否有超出红色线条的像素
                row_has_defect = False
                defect_pixels = []  # 记录超出红线的像素位置
                
                # 扫描有效区域内的每一列
                for col in range(int(effective_start_x), int(effective_end_x)):
                    # 检查像素是否为黑色（波形）
                    pixel = lower_half[row, col]
                    # 检查是否为黑色像素（BGR格式）
                    if pixel[0] < 50 and pixel[1] < 50 and pixel[2] < 50:
                        # 检查是否超出红色线条
                        if col < red_left or col > red_right:
                            row_has_defect = True
                            defect_pixels.append(col)
                
                if row_has_defect:
                    all_defect_rows.append({
                        'row': row,
                        'defect_pixels': defect_pixels,
                        'min_col': min(defect_pixels) if defect_pixels else 0,
                        'max_col': max(defect_pixels) if defect_pixels else 0
                    })
                    
                    if current_defect_start is None:
                        current_defect_start = row
                    current_defect_end = row
                else:
                    # 当前行没有缺陷，结束当前连续段
                    if current_defect_start is not None:
                        defect_duration = current_defect_end - current_defect_start + 1
                        if defect_duration > duration:
                            # 检查这个连续段是否形成斜线
                            segment_defect_rows = [d for d in all_defect_rows if current_defect_start <= d['row'] <= current_defect_end]
                            if not self.is_multi_row_straight_line(segment_defect_rows):
                                defect_rows.append({
                                    'start_row': current_defect_start,
                                    'end_row': current_defect_end,
                                    'duration': defect_duration,
                                    'region_idx': region_idx
                                })
                                if DEBUG_PRINT:
                                    print(f"    检测到缺陷行段: y={current_defect_start + height//2}-{current_defect_end + height//2}, 持续{defect_duration}行")
                            else:
                                if DEBUG_PRINT:
                                    print(f"    排除斜线: y={current_defect_start + height//2}-{current_defect_end + height//2}, 持续{defect_duration}行")
                        else:
                            pass
                            # print(f"    持续时间不足: y={current_defect_start + height//2}-{current_defect_end + height//2}, 持续{defect_duration}行 < {duration}")
                        current_defect_start = None
                        current_defect_end = None
            
            # 检查最后一个连续段
            # if current_defect_start is not None:
            #     defect_duration = current_defect_end - current_defect_start + 1
            #     if defect_duration > duration:
            #         # 检查这个连续段是否形成斜线
            #         segment_defect_rows = [d for d in all_defect_rows if current_defect_start <= d['row'] <= current_defect_end]
            #         if not is_multi_row_straight_line(segment_defect_rows):
            #             defect_rows.append({
            #                 'start_row': current_defect_start,
            #                 'end_row': current_defect_end,
            #                 'duration': defect_duration,
            #                 'region_idx': region_idx
            #             })
            #             print(f"    检测到缺陷行段: y={current_defect_start + height//2}-{current_defect_end + height//2}, 持续{defect_duration}行")
            #         else:
            #             print(f"    排除斜线: y={current_defect_start + height//2}-{current_defect_end + height//2}, 持续{defect_duration}行")
            #     else:
            #         print(f"    持续时间不足: y={current_defect_start + height//2}-{current_defect_end + height//2}, 持续{defect_duration}行 < {duration}")
            
            if DEBUG_PRINT:
                print(f"  区域{region_idx}缺陷行段数: {len(defect_rows)}")
            total_defect_segments.extend(defect_rows)
        
        if DEBUG_PRINT:
            print(f"\n=== 逐行缺陷分析完成 ===")
            print(f"总缺陷行段数: {len(total_defect_segments)}")
        
        # 判断是否存在缺陷
        if total_defect_segments:
            return True, f"检测到{len(total_defect_segments)}个缺陷行段", total_defect_segments
        else:
            return False, "未检测到缺陷", []

    def get_defect_detections(self, image, defect_segments):
        """
        根据缺陷行段生成检测框信息（仿 YOLO 格式）
        
        参数:
        - image: 原始图像
        - defect_segments: 缺陷行段列表，每个元素包含 region_idx, start_row, end_row
        
        返回:
        - result_boxes: list of [x1, y1, x2, y2]
        - result_scores: list of float，全部设为1.0（可根据需求调整）
        - result_class_id: list of str，全部设为 'defect'
        """
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

            # 取中心60%作为有效区域
            effective_width = region_width * 0.6
            effective_start_x = region_start_x + (region_width - effective_width) // 2
            effective_end_x = effective_start_x + effective_width

            # 纵向坐标
            start_y = lower_half_start + start_row
            end_y = lower_half_start + end_row

            # 添加到结果列表
            result_boxes.append([int(effective_start_x), int(start_y), int(effective_end_x), int(end_y)])
            result_scores.append(1.0)  # 缺陷置信度可以固定为1
            result_class_id.append(0)  # id可以固定为0

        return result_boxes, result_scores, result_class_id


    def infer(self, image):
        duration = 4
        
        red_lines_by_region = self.detect_red_lines(image)
        
        has_defect, message, defect_segments = self.analyze_defect_pattern_by_rows(image, red_lines_by_region, duration)
        
        result_boxes, result_scores, result_class_id = self.get_defect_detections(image, defect_segments)
        
        return result_boxes, result_scores, result_class_id
        

    def __call__(self, images: List[np.ndarray]):
        output = []

        for image in images:
            output.append(self.infer(image))

        return output
    