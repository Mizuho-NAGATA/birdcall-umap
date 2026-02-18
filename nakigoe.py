import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import threading

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd
import soundfile as sf
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

print("抽出された鳴き声区間:", len(segments))

# ===== スペクトログラム表示 =====
output_dir = "cluster_segments"
os.makedirs(output_dir, exist_ok=True)

plt.figure(figsize=(12, 4))
D = librosa.amplitude_to_db(
    np.abs(librosa.stft(y, n_fft=2048, hop_length=512)), ref=np.max
)
librosa.display.specshow(D, sr=sr, x_axis="time", y_axis="hz")
plt.colorbar(format="%+2.0f dB")
plt.title("Spectrogram (Full Audio)")
plt.tight_layout()

# 画像を保存
spectrogram_path = os.path.join(output_dir, "spectrogram_full_audio.png")
plt.savefig(spectrogram_path, dpi=150, bbox_inches="tight")
print(f"フルオーディオのスペクトログラムを保存しました: {spectrogram_path}")

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

        # 無音判定
        if np.max(np.abs(frame)) < 0.01:
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


# ===== フレームフィルタリングGUI =====
class FrameFilteringGUI:
    def __init__(self, y, sr, frame_times, mfcc_array, labels, frame_length):
        self.y = y
        self.sr = sr
        self.frame_times = frame_times
        self.mfcc_array = mfcc_array
        self.labels = labels
        self.frame_length = frame_length
        
        # フレームを除外するかのフラグ（True=残す, False=除外）
        self.keep_flags = [True] * len(frame_times)
        self.current_index = 0
        self.is_playing = False
        self.auto_play_mode = False
        self.finished = False
        
        # GUIウィンドウの作成
        self.root = tk.Tk()
        self.root.title("フレームフィルタリング - 鳥の鳴き声選別")
        self.root.geometry("700x500")
        
        # フレーム情報表示
        info_frame = ttk.Frame(self.root, padding="10")
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        self.info_label = tk.Label(
            info_frame,
            text="",
            font=("Arial", 14),
            justify=tk.LEFT,
            wraplength=650
        )
        self.info_label.pack(pady=20)
        
        # 進捗表示
        self.progress_label = tk.Label(
            info_frame,
            text="",
            font=("Arial", 12),
            fg="blue"
        )
        self.progress_label.pack(pady=10)
        
        # ボタンフレーム
        button_frame = ttk.Frame(self.root, padding="10")
        button_frame.pack(pady=20)
        
        # ナビゲーションボタン（前へ・次へ）
        nav_frame = ttk.Frame(button_frame)
        nav_frame.grid(row=0, column=0, columnspan=3, pady=10)
        
        self.prev_btn = ttk.Button(
            nav_frame,
            text="◀ 前へ",
            command=self.play_prev,
            width=15
        )
        self.prev_btn.grid(row=0, column=0, padx=10, pady=5)
        
        self.next_btn = ttk.Button(
            nav_frame,
            text="次へ ▶",
            command=self.play_next,
            width=15
        )
        self.next_btn.grid(row=0, column=1, padx=10, pady=5)
        
        # 再生ボタン
        self.play_btn = ttk.Button(
            button_frame,
            text="▶ 再生",
            command=self.play_current,
            width=15
        )
        self.play_btn.grid(row=1, column=0, padx=10, pady=5)
        
        # 除外ボタン
        self.exclude_btn = ttk.Button(
            button_frame,
            text="✗ 除外",
            command=self.exclude_current,
            width=15
        )
        self.exclude_btn.grid(row=1, column=1, padx=10, pady=5)
        
        # 保存ボタン
        self.save_btn = ttk.Button(
            button_frame,
            text="💾 保存",
            command=self.save_current_frame,
            width=15
        )
        self.save_btn.grid(row=1, column=2, padx=10, pady=5)
        
        # 全再生ボタン
        self.auto_play_btn = ttk.Button(
            button_frame,
            text="▶▶ 全再生",
            command=self.start_auto_play,
            width=15
        )
        self.auto_play_btn.grid(row=2, column=0, padx=10, pady=5)
        
        # 完了ボタン
        self.finish_btn = ttk.Button(
            button_frame,
            text="✓ 完了",
            command=self.finish_filtering,
            width=15
        )
        self.finish_btn.grid(row=2, column=1, padx=10, pady=5)
        
        # 停止ボタン
        self.stop_btn = ttk.Button(
            button_frame,
            text="■ 停止",
            command=self.stop_auto_play,
            width=15,
            state=tk.DISABLED
        )
        self.stop_btn.grid(row=2, column=2, padx=10, pady=5)
        
        # 使い方の説明
        help_text = (
            "使い方：\n"
            "・「前へ」「次へ」: フレームを移動して自動再生\n"
            "・「再生」: 現在のフレームを再生\n"
            "・「除外」: 現在のフレームを除外リストに追加\n"
            "・「保存」: 現在のフレームをファイルに保存\n"
            "・「全再生」: すべてのフレームを順番に再生\n"
            "・「完了」: フィルタリングを終了してUMAP可視化へ"
        )
        help_label = tk.Label(
            self.root,
            text=help_text,
            font=("Arial", 9),
            justify=tk.LEFT,
            fg="gray"
        )
        help_label.pack(pady=10)
        
        # 初期表示を更新
        self.update_info()
    
    def update_info(self):
        """現在のフレーム情報を更新"""
        if self.current_index >= len(self.frame_times):
            self.info_label.config(
                text="すべてのフレームを確認しました。\n「完了」をクリックしてください。"
            )
            self.play_btn.config(state=tk.DISABLED)
            self.exclude_btn.config(state=tk.DISABLED)
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)
            self.auto_play_btn.config(state=tk.DISABLED)
            self.save_btn.config(state=tk.DISABLED)
            return
        
        frame_time = self.frame_times[self.current_index]
        cluster = self.labels[self.current_index]
        status = "保持" if self.keep_flags[self.current_index] else "除外済み"
        excluded_count = sum(1 for f in self.keep_flags if not f)
        
        info_text = (
            f"フレーム {self.current_index + 1} / {len(self.frame_times)}\n"
            f"時間: {frame_time:.2f} 秒\n"
            f"クラスタ: {cluster}\n"
            f"状態: {status}"
        )
        self.info_label.config(text=info_text)
        
        progress_text = f"除外済み: {excluded_count} / {len(self.frame_times)}"
        self.progress_label.config(text=progress_text)
        
        # 前へボタンの有効/無効を制御
        if self.current_index == 0:
            self.prev_btn.config(state=tk.DISABLED)
        else:
            self.prev_btn.config(state=tk.NORMAL)
        
        # 次へボタンの有効/無効を制御
        if self.current_index >= len(self.frame_times) - 1:
            self.next_btn.config(state=tk.DISABLED)
        else:
            self.next_btn.config(state=tk.NORMAL)
    
    def play_current(self):
        """現在のフレームを再生"""
        if self.current_index >= len(self.frame_times):
            return
        
        if self.is_playing:
            return
        
        def play_audio():
            self.is_playing = True
            self.play_btn.config(state=tk.DISABLED)
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)
            
            try:
                frame_time = self.frame_times[self.current_index]
                start_sample = int(frame_time * self.sr)
                end_sample = min(start_sample + self.frame_length, len(self.y))
                frame_audio = self.y[start_sample:end_sample]
                
                # 音声再生
                sd.play(frame_audio, self.sr)
                sd.wait()
            except Exception as e:
                print(f"再生エラー: {e}")
            finally:
                self.is_playing = False
                self.play_btn.config(state=tk.NORMAL)
                self.update_info()
        
        thread = threading.Thread(target=play_audio, daemon=True)
        thread.start()
    
    def play_prev(self):
        """前のフレームに移動して再生"""
        if self.current_index <= 0:
            return
        
        self.current_index -= 1
        self.update_info()
        self.play_current()
    
    def play_next(self):
        """次のフレームに移動して再生"""
        if self.current_index >= len(self.frame_times) - 1:
            return
        
        self.current_index += 1
        self.update_info()
        self.play_current()
    
    def exclude_current(self):
        """現在のフレームを除外"""
        if self.current_index >= len(self.frame_times):
            return
        
        self.keep_flags[self.current_index] = False
        self.update_info()
    
    def save_current_frame(self):
        """現在のフレームをファイルに保存"""
        if self.current_index >= len(self.frame_times):
            messagebox.showwarning("警告", "保存するフレームがありません。")
            return
        
        # ファイル保存ダイアログを開く
        file_path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")],
            initialfile=f"frame_{self.current_index}_{self.labels[self.current_index]}.wav"
        )
        
        if not file_path:
            return  # キャンセルされた場合
        
        try:
            frame_time = self.frame_times[self.current_index]
            start_sample = int(frame_time * self.sr)
            end_sample = min(start_sample + self.frame_length, len(self.y))
            frame_audio = self.y[start_sample:end_sample]
            
            # WAVファイルに保存
            sf.write(file_path, frame_audio, self.sr)
            messagebox.showinfo("保存完了", f"フレームを保存しました：\n{file_path}")
            print(f"フレーム {self.current_index} を保存: {file_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"保存に失敗しました：\n{e}")
            print(f"保存エラー: {e}")
    
    def start_auto_play(self):
        """全フレームを自動再生"""
        self.auto_play_mode = True
        self.auto_play_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.play_btn.config(state=tk.DISABLED)
        self.exclude_btn.config(state=tk.DISABLED)
        self.prev_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        
        def auto_play():
            try:
                while self.auto_play_mode and self.current_index < len(self.frame_times):
                    frame_time = self.frame_times[self.current_index]
                    start_sample = int(frame_time * self.sr)
                    end_sample = min(start_sample + self.frame_length, len(self.y))
                    frame_audio = self.y[start_sample:end_sample]
                    
                    # GUIを更新
                    self.root.after(0, self.update_info)
                    
                    # 音声再生
                    sd.play(frame_audio, self.sr)
                    sd.wait()
                    
                    # 次のフレームへ
                    self.current_index += 1
            except Exception as e:
                print(f"自動再生エラー: {e}")
            finally:
                # 終了時の処理
                self.root.after(0, self.stop_auto_play)
        
        thread = threading.Thread(target=auto_play, daemon=True)
        thread.start()
    
    def stop_auto_play(self):
        """自動再生を停止"""
        self.auto_play_mode = False
        sd.stop()
        self.auto_play_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.play_btn.config(state=tk.NORMAL)
        self.exclude_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL)
        self.update_info()
    
    def finish_filtering(self):
        """フィルタリングを完了"""
        self.finished = True
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """GUIを表示して実行"""
        self.root.mainloop()
        return self.keep_flags


# フィルタリングGUIを起動
print("\n===== フレームフィルタリング =====")
print("GUIでフレームをフィルタリングします...")
gui = FrameFilteringGUI(y, sr, frame_times, mfcc_array, labels, frame_length)
keep_flags = gui.run()

# フィルタリング結果を適用
filtered_indices = [i for i in range(len(keep_flags)) if keep_flags[i]]
frame_times = [frame_times[i] for i in filtered_indices]
mfcc_array = mfcc_array[filtered_indices]
labels = labels[filtered_indices]

print(f"フィルタリング完了: {len(filtered_indices)} / {len(keep_flags)} フレームを保持")

# ===== UMAP 可視化 =====
umap = UMAP(n_components=2, random_state=0)
points = umap.fit_transform(mfcc_array)

plt.figure(figsize=(8, 6))
plt.scatter(points[:, 0], points[:, 1], c=labels, cmap="tab10")
plt.title("Bird Call Clustering (UMAP)")
plt.xlabel("UMAP Dimension 1")
plt.ylabel("UMAP Dimension 2")

# 画像を保存
umap_path = os.path.join(output_dir, "cluster_visualization_umap.png")
plt.savefig(umap_path, dpi=150, bbox_inches="tight")
print(f"UMAP可視化を保存しました: {umap_path}")

plt.show()

# ===== クラスタごとの代表鳴き声（segment全体）を保存 =====
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

# 画像を保存
spectrograms_path = os.path.join(output_dir, "cluster_spectrograms.png")
plt.savefig(spectrograms_path, dpi=150, bbox_inches="tight")
print(f"クラスタスペクトログラムを保存しました: {spectrograms_path}")

plt.show()

# ===== クラスタごとの時間帯を表示 =====
for c in range(k):
    print(f"\nクラスタ {c}:")
    times = [frame_times[i] for i in range(len(labels)) if labels[i] == c]
    print(times[:100])  # 最初の100個だけ表示
