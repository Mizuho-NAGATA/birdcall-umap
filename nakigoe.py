import tkinter as tk
from tkinter import filedialog

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import KMeans
from umap import UMAP

# ===== ファイル選択ダイアログ =====
root = tk.Tk()
root.withdraw()  # ウィンドウを表示しない

file_path = filedialog.askopenfilename(
    title="WAVファイルを選択してください",
    filetypes=[("WAV files", "*.wav"), ("All files", "*.*")],
)

if not file_path:
    print("ファイルが選択されませんでした。")
    exit()

print("選択されたファイル:", file_path)

# ===== 音声読み込み =====
y, sr = librosa.load(file_path, sr=None)
print("録音時間:", len(y) / sr, "秒")

# ===== 0.2秒ごとにフレーム分割 =====
frame_length = int(sr * 0.2)
hop_length = int(sr * 0.2)

mfcc_list = []
time_list = []  # 各フレームの開始時刻（秒）を記録

for i in range(0, len(y), hop_length):
    frame = y[i : i + frame_length]
    if len(frame) < frame_length:
        break

    if np.max(np.abs(frame)) < 0.01:
        continue

    mfcc = librosa.feature.mfcc(y=frame, sr=sr, n_mfcc=20)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)
    feature = np.concatenate([mfcc_mean, mfcc_std])
    mfcc_list.append(feature)
    time_list.append(i / sr)  # サンプル位置を秒に変換

mfcc_array = np.array(mfcc_list)
time_array = np.array(time_list)
print("抽出フレーム数:", len(mfcc_array))
print("特徴量 shape:", mfcc_array.shape)
print("時間範囲:", f"{time_array[0]:.2f}秒 〜 {time_array[-1]:.2f}秒")

# ===== クラスタリング =====
k = 4
kmeans = KMeans(n_clusters=k, random_state=0)
labels = kmeans.fit_predict(mfcc_array)

# ===== UMAP 可視化 =====
umap = UMAP(n_components=2, random_state=0)
points = umap.fit_transform(mfcc_array)

plt.figure(figsize=(10, 8))
# 時間を色で表示（カラーバー付き）
scatter = plt.scatter(points[:, 0], points[:, 1], c=time_array, cmap="viridis", 
                     s=50, alpha=0.7, edgecolors='black', linewidths=0.5)
plt.colorbar(scatter, label="時間 (秒)")
plt.title("鳴き声クラスタリング (UMAP) - 色：時間経過")
plt.xlabel("UMAP 第1次元")
plt.ylabel("UMAP 第2次元")

# クラスタ情報も表示
plt.figure(figsize=(10, 8))
plt.scatter(points[:, 0], points[:, 1], c=labels, cmap="tab10", 
           s=50, alpha=0.7, edgecolors='black', linewidths=0.5)
plt.colorbar(label="クラスタ")
plt.title("鳴き声クラスタリング (UMAP) - 色：クラスタ")
plt.xlabel("UMAP 第1次元")
plt.ylabel("UMAP 第2次元")

plt.show()
