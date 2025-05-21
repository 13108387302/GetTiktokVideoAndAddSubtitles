import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import numpy as np
import subprocess

def create_static_text_image(
    frame,
    chinese_text,
    font_path_chinese,
    chinese_text_size=10,
    chinese_text_color=(0,0,0),
    chinese_text_posotion=1.75,
    line_spacing=1.5,
    ):
    """
    直接在帧上添加文字和模糊背景
    
    参数:
        frame: 输入的帧（numpy数组）
        chinese_text: 要添加的中文文字
        font_path_chinese: 中文字体路径
        chinese_text_size: 文字大小
        chinese_text_color: 文字颜色
        chinese_text_posotion: 文字位置
        line_spacing: 行间距
    """
    height, width = frame.shape[:2]
    # 转换为PIL格式
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    # 自动计算中文字体大小
    font_size_chinese = min(width, height) // chinese_text_size
    font_chinese = ImageFont.truetype(font_path_chinese, font_size_chinese)
    # 获取中文字体度量
    ascent_chinese, descent_chinese = font_chinese.getmetrics()
    base_line_height_chinese = ascent_chinese + descent_chinese  # 基础行高（无额外间距）
    actual_line_height_chinese = int(base_line_height_chinese * line_spacing)  # 实际行高（含间距）
    
    # 自动换行处理中文文本
    max_width = int(width * 0.8)
    lines_chinese = []
    current_line_chinese = []
    current_width_chinese = 0
    for char in chinese_text:
        char_width = font_chinese.getlength(char)
        if current_width_chinese + char_width > max_width:
            lines_chinese.append(''.join(current_line_chinese))
            current_line_chinese = [char]
            current_width_chinese = char_width
        else:
            current_line_chinese.append(char)
            current_width_chinese += char_width
    lines_chinese.append(''.join(current_line_chinese))
    
    # 计算中文文本总高度（考虑行间距）
    total_height_chinese = (len(lines_chinese) - 1) * actual_line_height_chinese + base_line_height_chinese
    # 计算文字位置（垂直居中）
    y_chinese = int((height - total_height_chinese) // chinese_text_posotion)
    
    # 定义模糊区域（扩大范围）
    blur_area = (
        0,  # x起点
        y_chinese - 40,  # y起点（上方留出空间）
        width,  # x终点（整个宽度）
        y_chinese + total_height_chinese + 40  # y终点（下方留出空间）
    )
    
    # 裁剪区域并进行多次模糊
    cropped = pil_img.crop(blur_area)
    for _ in range(5):  # 增加模糊次数
        cropped = cropped.filter(ImageFilter.GaussianBlur(radius=15))
    
    # 将模糊后的区域粘贴回原图
    pil_img.paste(cropped, blur_area)
    
    # 重新创建draw对象
    draw = ImageDraw.Draw(pil_img)
    
    # 绘制文字（带阴影）
    shadow_color = (0, 0, 0, 150)  # 阴影颜色
    
    for line in lines_chinese:
        line_width_chinese = font_chinese.getlength(line)
        x_chinese = int((width - line_width_chinese) // 2)
        # 绘制阴影
        draw.text((x_chinese+2, y_chinese+2), line, font=font_chinese, fill=shadow_color)
        # 绘制主文字
        draw.text((x_chinese, y_chinese), line, font=font_chinese, fill=chinese_text_color)
        y_chinese += actual_line_height_chinese
    
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

