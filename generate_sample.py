"""
640x480 サンプルグレースケール画像を生成
- ヒストグラムに3つの山（255側に偏り）
- 80未満の輝度は存在しない
"""

import numpy as np
from PIL import Image, ImageFilter

rng = np.random.default_rng(42)

width, height = 640, 480

# --- 3つのガウス分布 (255側に偏り、80未満なし) ---
# 山1: 中心=110, σ=5   (最も低いが80以上)
# 山2: 中心=175, σ=6   (中間)
# 山3: 中心=230, σ=5   (高輝度)
means  = [110, 175, 230]
stds   = [5,   6,   5]

# --- Voronoi的に3領域にハード分割 ---
region_centers = [
    (120, 370),   # 左下: 山1
    (320, 200),   # 中央: 山2
    (540, 100),   # 右上: 山3
]

structured = np.zeros((height, width), dtype=np.uint8)

for y in range(height):
    for x in range(width):
        dists = [np.sqrt((x - cx)**2 + (y - cy)**2) for cx, cy in region_centers]
        chosen = int(np.argmin(dists))
        val = rng.normal(means[chosen], stds[chosen])
        structured[y, x] = int(np.clip(val, 80, 255))

# 境界を滑らかにする軽いぼかし(半径小さめ)
img = Image.fromarray(structured)
img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
structured = np.array(img)
structured = np.clip(structured, 80, 255).astype(np.uint8)

img = Image.fromarray(structured)
img.save('sample_grayscale.png')

# ヒストグラム確認
hist = np.bincount(structured.flatten(), minlength=256)
print("画像を保存しました: sample_grayscale.png")
print(f"サイズ: {width}x{height}")
print(f"最小輝度: {structured.min()}")
print(f"最大輝度: {structured.max()}")
print(f"80未満のピクセル数: {np.sum(structured < 80)}")

from scipy.signal import find_peaks
peaks, props = find_peaks(hist, height=300, distance=15)
print(f"ヒストグラムのピーク位置: {peaks}")
print(f"各ピークの高さ: {hist[peaks]}")
