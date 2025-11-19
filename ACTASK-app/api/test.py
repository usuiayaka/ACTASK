calendar_coords_list_48 = []

# グリッド設定
num_cols = 8 # 横8列
num_rows = 6 # 縦6行

# 全体範囲 (上下左右 2% の余白)
x_start = 0.02
x_end = 0.98
y_start = 0.02
y_end = 0.98

# 各マス目の幅と高さの計算
# 幅: 0.96 / 8 = 0.12
cell_width = (x_end - x_start) / num_cols
# 高さ: 0.96 / 6 = 0.16
cell_height = (y_end - y_start) / num_rows

day_counter = 1

for row in range(num_rows):
    for col in range(num_cols):
        # x座標の計算
        x_min = x_start + col * cell_width
        x_max = x_min + cell_width
        
        # y座標の計算
        y_min = y_start + row * cell_height
        y_max = y_min + cell_height
        
        # 辞書を作成し、リストに追加
        calendar_coords_list_48.append({
            "day": day_counter,
            # 座標は [x_min, y_min, x_max, y_max] の順に小数点以下4桁で丸める
            "box": [round(x_min, 4), round(y_min, 4), round(x_max, 4), round(y_max, 4)]
        })
        
        day_counter += 1

# データの出力（Pythonのリスト形式）
print(calendar_coords_list_48)