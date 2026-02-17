import os
import tkinter as tk
from tkinter import filedialog

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import KMeans
from umap import UMAP

# ===== フィルタリング設定 =====
# 非鳥類音声フィルタのパラメータ
MIN_SPECTRAL_CENTROID_HZ = 2500  # スペクトル重心の最小値（人の声、低周波ノイズを除外）
MIN_ZERO_CROSSING_RATE = 0.1  # ゼロ交差率の最小値（持続的な低音を除外）
MIN_RMS_ENERGY = 0.005  # RMSエネルギーの最小値（ノイズレベルを除外）
MIN_SPECTRAL_ROLLOFF_HZ = 3500  # スペクトルロールオフの最小値（低周波ノイズを除外）

# 無音判定のパラメータ
MIN_FRAME_AMPLITUDE = 0.01  # フレームの最大振幅の最小値
MIN_FRAME_ENERGY = 0.0001  # フレームのエネルギーの最小値
MIN_FRAME_ZCR = 0.05  # フレームのゼロ交差率の最小値

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

# ===== 高周波だけを残すハイパスフィルタ =====
import scipy.signal as signal

cutoff = 3000  # 3000Hz以上を残す
b, a = signal.butter(4, cutoff / (sr / 2), btype="high")
y = signal.filtfilt(b, a, y)
print("ハイパスフィルタ適用完了（3000Hz以上を抽出）")

# ===== 鳴き声のある区間だけを抽出 =====
intervals = librosa.effects.split(y, top_db=45)  # 25〜35が鳥に最適

segments = []
for start, end in intervals:
    duration = (end - start) / sr
    if duration >= 0.1:  # 0.1秒以上の音だけ採用
        segments.append((start, end))

print("初期抽出区間:", len(segments))

# ===== 非鳥類音声の除外 =====
# 鳥の声の特徴を用いて非鳥類音声（人の声、環境音など）をフィルタリング
filtered_segments = []
for start, end in segments:
    segment = y[start:end]
    
    # 特徴量の計算
    # 1. ゼロ交差率（Zero Crossing Rate）: 鳥の声は高い値を示す傾向
    zcr = librosa.feature.zero_crossing_rate(segment)[0]
    zcr_mean = np.mean(zcr)
    
    # 2. スペクトル重心（Spectral Centroid）: 鳥の声は高周波に集中
    spectral_centroids = librosa.feature.spectral_centroid(y=segment, sr=sr)[0]
    spectral_centroid_mean = np.mean(spectral_centroids)
    
    # 3. スペクトルロールオフ（Spectral Rolloff）: エネルギーの85%が含まれる周波数
    spectral_rolloff = librosa.feature.spectral_rolloff(y=segment, sr=sr, roll_percent=0.85)[0]
    spectral_rolloff_mean = np.mean(spectral_rolloff)
    
    # 4. RMS エネルギー
    rms = librosa.feature.rms(y=segment)[0]
    rms_mean = np.mean(rms)
    
    # フィルタリング条件
    # 鳥の声の特徴:
    # - ゼロ交差率が高い
    # - スペクトル重心が高い（高周波に集中）
    # - 適度なRMSエネルギー
    # - スペクトルロールオフが高い
    
    is_bird_sound = True
    
    # 人の声や低周波ノイズを除外
    if spectral_centroid_mean < MIN_SPECTRAL_CENTROID_HZ:
        is_bird_sound = False
    
    # ゼロ交差率が低すぎる場合（持続的な低音ノイズ）
    if zcr_mean < MIN_ZERO_CROSSING_RATE:
        is_bird_sound = False
    
    # RMSエネルギーが低すぎる場合（ノイズレベル）
    if rms_mean < MIN_RMS_ENERGY:
        is_bird_sound = False
    
    # スペクトルロールオフが低すぎる場合（低周波ノイズ）
    if spectral_rolloff_mean < MIN_SPECTRAL_ROLLOFF_HZ:
        is_bird_sound = False
    
    if is_bird_sound:
        filtered_segments.append((start, end))

segments = filtered_segments
print("非鳥類音声除外後:", len(segments), "区間")

# ===== スペクトログラム表示 =====
plt.figure(figsize=(12, 4))
D = librosa.amplitude_to_db(
    np.abs(librosa.stft(y, n_fft=2048, hop_length=512)), ref=np.max
)
librosa.display.specshow(D, sr=sr, x_axis="time", y_axis="hz")
plt.colorbar(format="%+2.0f dB")
plt.title("Spectrogram (Full Audio)")
plt.tight_layout()
plt.show()

# ===== 鳴き声区間だけをフレーム分割 =====
frame_length = int(sr * 0.2)
hop_length = int(sr * 0.2)

mfcc_list = []
frame_times = []

for start, end in segments:
    segment = y[start:end]

    for i in range(0, len(segment), hop_length):
        frame = segment[i : i + frame_length]
        if len(frame) < frame_length:
            break

        # 無音判定（強化版）
        # 1. 振幅ベースの判定
        max_amplitude = np.max(np.abs(frame))
        if max_amplitude < MIN_FRAME_AMPLITUDE:
            continue
        
        # 2. エネルギーベースの判定
        energy = np.sum(frame ** 2) / len(frame)
        if energy < MIN_FRAME_ENERGY:
            continue
        
        # 3. ゼロ交差率での判定（ノイズフロア検出）
        frame_zcr = librosa.feature.zero_crossing_rate(frame)[0]
        if np.mean(frame_zcr) < MIN_FRAME_ZCR:
            continue

        # 元の録音時間に戻す
        frame_times.append((start + i) / sr)

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

# ===== クラスタごとの代表鳴き声（segment全体）を保存 =====
import soundfile as sf

output_dir = "cluster_segments"
os.makedirs(output_dir, exist_ok=True)

num_samples = 10  # 保存する代表音の数

for c in range(k):
    idx_list = [i for i in range(len(labels)) if labels[i] == c]

    if len(idx_list) == 0:
        print(f"クラスタ {c} にはフレームがありません")
        continue

    print(
        f"クラスタ {c}: {len(idx_list)} 個のフレームから {num_samples} 個の区間を保存"
    )

    used_segments = set()

    count = 0
    for idx in idx_list:
        if count >= num_samples:
            break

        frame_time = frame_times[idx]

        # このフレームが属する鳴き声区間（segment）を探す
        for seg_i, (start, end) in enumerate(segments):
            if start / sr <= frame_time <= end / sr:
                if seg_i in used_segments:
                    break  # 同じ区間は保存しない

                used_segments.add(seg_i)
                count += 1

                segment_audio = y[start:end]
                out_path = f"{output_dir}/cluster_{c}_seg{seg_i}.wav"
                sf.write(out_path, segment_audio, sr)

                print(f"  → 区間 {seg_i} を保存: {out_path}")
                break
# ===== クラスタごとの代表スペクトログラムを並べて表示（10個） =====
import librosa.display
import matplotlib.pyplot as plt

num_samples = 10  # 表示する代表音の数

plt.figure(figsize=(20, 10))

plot_index = 1

for c in range(k):
    idx_list = [i for i in range(len(labels)) if labels[i] == c]
    if len(idx_list) == 0:
        continue

    for n, idx in enumerate(idx_list[:num_samples]):
        start_time = frame_times[idx]
        start_sample = int(start_time * sr)
        end_sample = start_sample + frame_length
        sample = y[start_sample:end_sample]

        D = librosa.amplitude_to_db(
            np.abs(librosa.stft(sample, n_fft=1024, hop_length=256)), ref=np.max
        )

        plt.subplot(k, num_samples, plot_index)
        librosa.display.specshow(D, sr=sr, x_axis="time", y_axis="hz")
        plt.title(f"C{c}-{n}")
        plot_index += 1

plt.tight_layout()
plt.show()

# ===== クラスタごとの時間帯を表示 =====
for c in range(k):
    print(f"\nクラスタ {c}:")
    times = [frame_times[i] for i in range(len(labels)) if labels[i] == c]
    print(times[:100])  # 最初の100個だけ表示
