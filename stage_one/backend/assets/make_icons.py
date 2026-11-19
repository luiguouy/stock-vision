# -*- coding: utf-8 -*-
"""
StockVision 桌面图标生成与精细抠底脚本
- 从 assets/bull_raw.jpg 智能抠除外部奶油白/浅灰棋盘背景与底部椭圆阴影
- 保留冲锋牛主体高光与角部高光细节
- 1px 抗锯齿平滑边缘羽化，消除白边
- 自动按 1:1 正方形安全边距裁剪居中
- 生成 app.png (RGBA) 以及 Windows 多尺寸合一图标 app.ico (16~256)
"""

import os
import struct
import cv2
import numpy as np
from PIL import Image

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_IMAGE_PATH = os.path.join(ASSETS_DIR, "bull_raw.jpg")
PNG_OUT_PATH = os.path.join(ASSETS_DIR, "app.png")
ICO_OUT_PATH = os.path.join(ASSETS_DIR, "app.ico")

def generate_icons():
    if not os.path.exists(RAW_IMAGE_PATH):
        raise FileNotFoundError(f"未找到原图: {RAW_IMAGE_PATH}")

    print(f"[IconGen] 读取原图: {RAW_IMAGE_PATH}")
    img = cv2.imread(RAW_IMAGE_PATH)
    h, w = img.shape[:2]

    # 1. 计算三通道色度差 (Chromatic difference)，识别低饱和度的背景格子与浅灰阴影
    b = img[:, :, 0].astype(np.int32)
    g = img[:, :, 1].astype(np.int32)
    r = img[:, :, 2].astype(np.int32)
    color_diff = np.maximum(np.maximum(np.abs(r - g), np.abs(g - b)), np.abs(r - b))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 外部棋盘格特征：高亮度且极低色度
    is_checker = (color_diff <= 10) & (gray > 195)
    # 底部椭圆阴影特征：位于冲锋牛下方(y >= 1610)，且亮度高于深色牛蹄(gray > 115)
    is_shadow = (np.arange(h)[:, None] >= 1610) & (np.arange(h)[:, None] <= 1765) & \
                (gray > 115) & (np.arange(w)[None, :] >= 240) & (np.arange(w)[None, :] <= 1600)

    is_bg_or_shadow = is_checker | is_shadow

    # 2. 外部连通域泛洪 (Connected Components Flood Fill from borders)
    # 确保只剔除与图像最外缘接触的外部背景，主体内部的所有高光区域、角部亮区绝不误删
    num_labels, labels = cv2.connectedComponents(is_bg_or_shadow.astype(np.uint8), connectivity=8)
    border_labels = set(np.unique(labels[[0, h - 1], :])) | set(np.unique(labels[:, [0, w - 1]]))
    is_external_bg = np.isin(labels, list(border_labels))

    # 前景主体掩码 (Foreground Mask)
    fg = ~is_external_bg
    fg_u8 = (fg.astype(np.uint8)) * 255

    # 3. 1px 形态学收缩与抗锯齿羽化 (Anti-aliasing feathering)
    # 彻底清除 JPEG 压缩引入的微弱灰白边缘杂色
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg_eroded = cv2.erode(fg_u8, kernel, iterations=1)
    alpha = cv2.GaussianBlur(fg_eroded, (3, 3), 0.7)

    # 4. 定位主体有效边界并自适应裁剪 (保留约 4% 安全边距)
    pts = np.argwhere(fg_eroded > 0)
    y_min, x_min = pts.min(axis=0)
    y_max, x_max = pts.max(axis=0)
    fg_h = y_max - y_min + 1
    fg_w = x_max - x_min + 1

    b_ch, g_ch, r_ch = cv2.split(img)
    rgba = cv2.merge([r_ch, g_ch, b_ch, alpha])
    cropped = rgba[y_min:y_max + 1, x_min:x_max + 1]

    # 正方形居中画板，主体占 92%（各边保留 4% 安全边距）
    dim = max(fg_w, fg_h)
    target_size = int(round(dim / 0.92))
    canvas = np.zeros((target_size, target_size, 4), dtype=np.uint8)

    y_offset = (target_size - fg_h) // 2
    x_offset = (target_size - fg_w) // 2
    canvas[y_offset:y_offset + fg_h, x_offset:x_offset + fg_w] = cropped

    # 5. 保存透明背景 app.png
    pil_img = Image.fromarray(canvas, mode="RGBA")
    pil_img.save(PNG_OUT_PATH, format="PNG")
    print(f"[IconGen] 已生成透明背景 PNG: {PNG_OUT_PATH} (尺寸: {pil_img.size})")

    # 6. 保存 Windows 多尺寸 ICO 文件
    # 包含 16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256
    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    pil_img.save(ICO_OUT_PATH, format="ICO", sizes=icon_sizes)
    print(f"[IconGen] 已生成多尺寸 ICO: {ICO_OUT_PATH}")

    # 校验生成的 ICO 文件结构
    with open(ICO_OUT_PATH, "rb") as f:
        header = f.read(6)
        reserved, ico_type, count = struct.unpack("<HHH", header)
        print(f"[IconGen] ICO 校验: 图标数量 = {count} 层")
        for i in range(count):
            entry = f.read(16)
            iw, ih, _, _, _, bpp, bytes_in_res, _ = struct.unpack("<BBBBHHII", entry)
            iw = 256 if iw == 0 else iw
            ih = 256 if ih == 0 else ih
            print(f"  - 尺寸层 {i+1}: {iw}x{ih}, 色深: {bpp}bpp, 大小: {bytes_in_res} 字节")

if __name__ == "__main__":
    generate_icons()
