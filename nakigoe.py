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

# ===== スペクトログラム表示 =====
plt.figure(figsize=(12, 4))
D = librosa.amplitude_to_db(
        np.abs(librosa.stft(y, n_fft=2048, hop_length=512)),
        ref=np.max
    )
librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='hz')
plt.colorbar(format='%+2.0f dB')
plt.title("Spectrogram (Full Audio)")
plt.tight_layout()
plt.show()

# ===== 0.2秒ごとにフレーム分割 =====
frame_length = int(sr * 0.2)
hop_length = int(sr * 0.2)

mfcc_list = []

for i in range(0, len(y), hop_length):
    frame = y[i : i + frame_length]
    if len(frame) < frame_length:
        break

    if np.max(np.abs(frame)) < 0.01:
        continue

    # 追加：このフレームの開始時間（秒）
    frame_times.append(i / sr)
    
    mfcc = librosa.feature.mfcc(y=frame, sr=sr, n_mfcc=20)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)
    feature = np.concatenate([mfcc_mean, mfcc_std])
    mfcc_list.append(feature)

mfcc_array = np.array(mfcc_list)
print("抽出フレーム数:", len(mfcc_array))
print("特徴量 shape:", mfcc_array.shape)

# ===== クラスタリング =====
k = 4
kmeans = KMeans(n_clusters=k, random_state=0)
labels = kmeans.fit_predict(mfcc_array)

# ===== UMAP 可視化 =====
umap = UMAP(n_components=2, random_state=0)
points = umap.fit_transform(mfcc_array)

plt.figure(figsize=(8, 6))
plt.scatter(points[:, 0], points[:, 1], c=labels, cmap="tab10")
plt.title("Bird Call Clustering (UMAP)")
plt.xlabel("UMAP Dimension 1")
plt.ylabel("UMAP Dimension 2")
plt.show()

# ===== クラスタごとの時間帯を表示 =====
for c in range(k):
    print(f"\nクラスタ {c}:")
    times = [frame_times[i] for i in range(len(labels)) if labels[i] == c]
    print(times[:10])  # 最初の10個だけ表示

