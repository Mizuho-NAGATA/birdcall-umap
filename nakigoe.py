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
import scipy.signal as signal


# ===== フレームフィルタリングGUI クラス定義 =====
class FrameFilteringGUI:
    def __init__(self, y, sr, frame_times, mfcc_array, labels, frame_length, processing_params):
        self.y = y
        self.sr = sr
        self.frame_times = frame_times
        self.mfcc_array = mfcc_array
        self.labels = labels
        self.frame_length = frame_length
        
        # パラメーター（現在の値を使用）
        self.param_frame_length = processing_params['frame_length_sec']
        self.param_hop_length = processing_params['hop_length_sec']
        self.param_cutoff = processing_params['cutoff']
        self.param_top_db = processing_params['top_db']
        
        # フレームを除外するかのフラグ（True=残す, False=除外）
        self.keep_flags = [True] * len(frame_times)
        self.current_index = 0
        self.is_playing = False
        self.auto_play_mode = False
        self.finished = False
        self.reprocess_requested = False
        
        # GUIウィンドウの作成
        self.root = tk.Tk()
        self.root.title("フレームフィルタリング - 鳥の鳴き声選別")
        self.root.geometry("700x750")
        
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
            text="💾 一括保存",
            command=self.save_all_frames,
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
            "・「一括保存」: 除外していないすべてのフレームをディレクトリに保存\n"
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
        
        # ===== パラメーター調整GUI =====
        param_frame = ttk.LabelFrame(self.root, text="パラメーター調整", padding="10")
        param_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=10)
        
        # フレーム長スライダー
        frame_length_frame = ttk.Frame(param_frame)
        frame_length_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(frame_length_frame, text="フレーム長:").pack(side=tk.LEFT, padx=5)
        self.frame_length_value_label = ttk.Label(
            frame_length_frame, 
            text=f"{self.param_frame_length:.2f} 秒",
            width=10
        )
        self.frame_length_value_label.pack(side=tk.LEFT, padx=5)
        
        self.frame_length_slider = tk.Scale(
            frame_length_frame,
            from_=0.1,
            to=0.5,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            length=300,
            command=self.update_frame_length
        )
        self.frame_length_slider.set(self.param_frame_length)
        self.frame_length_slider.pack(side=tk.LEFT, padx=5)
        
        # ホップ長スライダー
        hop_length_frame = ttk.Frame(param_frame)
        hop_length_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(hop_length_frame, text="ホップ長:").pack(side=tk.LEFT, padx=5)
        self.hop_length_value_label = ttk.Label(
            hop_length_frame,
            text=f"{self.param_hop_length:.2f} 秒",
            width=10
        )
        self.hop_length_value_label.pack(side=tk.LEFT, padx=5)
        
        self.hop_length_slider = tk.Scale(
            hop_length_frame,
            from_=0.1,
            to=0.5,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            length=300,
            command=self.update_hop_length
        )
        self.hop_length_slider.set(self.param_hop_length)
        self.hop_length_slider.pack(side=tk.LEFT, padx=5)
        
        # ハイパスフィルタ周波数スライダー
        cutoff_frame = ttk.Frame(param_frame)
        cutoff_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(cutoff_frame, text="ハイパスフィルタ:").pack(side=tk.LEFT, padx=5)
        self.cutoff_value_label = ttk.Label(
            cutoff_frame,
            text=f"{self.param_cutoff} Hz",
            width=10
        )
        self.cutoff_value_label.pack(side=tk.LEFT, padx=5)
        
        self.cutoff_slider = tk.Scale(
            cutoff_frame,
            from_=1000,
            to=6000,
            resolution=100,
            orient=tk.HORIZONTAL,
            length=300,
            command=self.update_cutoff
        )
        self.cutoff_slider.set(self.param_cutoff)
        self.cutoff_slider.pack(side=tk.LEFT, padx=5)
        
        # エネルギー閾値スライダー
        top_db_frame = ttk.Frame(param_frame)
        top_db_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(top_db_frame, text="エネルギー閾値:").pack(side=tk.LEFT, padx=5)
        self.top_db_value_label = ttk.Label(
            top_db_frame,
            text=f"{self.param_top_db}",
            width=10
        )
        self.top_db_value_label.pack(side=tk.LEFT, padx=5)
        
        self.top_db_slider = tk.Scale(
            top_db_frame,
            from_=20,
            to=60,
            resolution=1,
            orient=tk.HORIZONTAL,
            length=300,
            command=self.update_top_db
        )
        self.top_db_slider.set(self.param_top_db)
        self.top_db_slider.pack(side=tk.LEFT, padx=5)
        
        # パラメーター適用ボタン
        apply_params_btn = ttk.Button(
            param_frame,
            text="パラメーター適用（再処理）",
            command=self.apply_parameters
        )
        apply_params_btn.pack(pady=10)
        
        # パラメーター情報テキスト
        param_info_text = (
            "注: パラメーターを変更後、「パラメーター適用」ボタンをクリックすると\n"
            "新しいパラメーターで音声処理を再実行します（GUIは一旦閉じます）"
        )
        param_info_label = tk.Label(
            param_frame,
            text=param_info_text,
            font=("Arial", 8),
            justify=tk.LEFT,
            fg="gray"
        )
        param_info_label.pack(pady=5)
        
        # 初期表示を更新
        self.update_info()
    
    def update_frame_length(self, value):
        """フレーム長パラメーターを更新"""
        self.param_frame_length = float(value)
        self.frame_length_value_label.config(text=f"{self.param_frame_length:.2f} 秒")
    
    def update_hop_length(self, value):
        """ホップ長パラメーターを更新"""
        self.param_hop_length = float(value)
        self.hop_length_value_label.config(text=f"{self.param_hop_length:.2f} 秒")
    
    def update_cutoff(self, value):
        """ハイパスフィルタ周波数パラメーターを更新"""
        self.param_cutoff = int(value)
        self.cutoff_value_label.config(text=f"{self.param_cutoff} Hz")
    
    def update_top_db(self, value):
        """エネルギー閾値パラメーターを更新"""
        self.param_top_db = int(value)
        self.top_db_value_label.config(text=f"{self.param_top_db}")
    
    def apply_parameters(self):
        """パラメーターを適用して再処理"""
        result = messagebox.askyesno(
            "パラメーター適用",
            "新しいパラメーターで音声処理を再実行します。\n"
            "現在のフィルタリング状態は失われます。\n"
            "続行しますか？"
        )
        if result:
            # パラメーターをグローバル変数に保存して再処理をトリガー
            self.finished = True
            self.reprocess_requested = True
            self.root.quit()
            self.root.destroy()
    
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
    
    def save_all_frames(self):
        """除外していないすべてのフレームを一括保存"""
        # 保存するフレームを確認
        frames_to_save = [i for i, keep in enumerate(self.keep_flags) if keep]
        
        if not frames_to_save:
            messagebox.showwarning("警告", "保存するフレームがありません。すべて除外されています。")
            return
        
        # 保存先ディレクトリを選択
        save_dir = filedialog.askdirectory(
            title="保存先ディレクトリを選択してください",
            initialdir=os.getcwd()
        )
        
        if not save_dir:
            return  # キャンセルされた場合
        
        try:
            saved_count = 0
            for i in frames_to_save:
                frame_time = self.frame_times[i]
                start_sample = int(frame_time * self.sr)
                end_sample = min(start_sample + self.frame_length, len(self.y))
                frame_audio = self.y[start_sample:end_sample]
                
                # ファイル名: frame_{index}_{cluster}.wav
                file_name = f"frame_{i}_{self.labels[i]}.wav"
                file_path = os.path.join(save_dir, file_name)
                
                # WAVファイルに保存
                sf.write(file_path, frame_audio, self.sr)
                saved_count += 1
                print(f"保存: {file_path}")
            
            messagebox.showinfo(
                "保存完了", 
                f"{saved_count} 個のフレームを保存しました：\n{save_dir}"
            )
            print(f"\n合計 {saved_count} 個のフレームを保存しました")
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
        return {
            'keep_flags': self.keep_flags,
            'reprocess_requested': self.reprocess_requested,
            'params': {
                'frame_length_sec': self.param_frame_length,
                'hop_length_sec': self.param_hop_length,
                'cutoff': self.param_cutoff,
                'top_db': self.param_top_db
            }
        }


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

# 出力ディレクトリの作成
output_dir = "cluster_segments"
os.makedirs(output_dir, exist_ok=True)

# ===== パラメーターの初期値 =====
processing_params = {
    'frame_length_sec': 0.2,
    'hop_length_sec': 0.2,
    'cutoff': 3000,
    'top_db': 45
}

# ===== メイン処理ループ =====
reprocess = True
first_run = True
while reprocess:
    reprocess = False  # デフォルトでは1回のみ実行
    
    # ===== 音声読み込み =====
    y_original, sr = librosa.load(file_path, sr=None)
    print(f"\n録音時間: {len(y_original) / sr:.2f} 秒")
    
    # ===== 高周波だけを残すハイパスフィルタ =====
    cutoff = processing_params['cutoff']
    b, a = signal.butter(4, cutoff / (sr / 2), btype="high")
    y = signal.filtfilt(b, a, y_original)
    print(f"ハイパスフィルタ適用完了（{cutoff}Hz以上を抽出）")
    
    # ===== 鳴き声のある区間だけを抽出 =====
    top_db = processing_params['top_db']
    intervals = librosa.effects.split(y, top_db=top_db)
    
    segments = []
    for start, end in intervals:
        duration = (end - start) / sr
        if duration >= 0.1:  # 0.1秒以上の音だけ採用
            segments.append((start, end))
    
    print(f"抽出された鳴き声区間: {len(segments)}")
    
    # ===== スペクトログラム表示（初回のみ） =====
    if first_run:
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
        first_run = False  # 初回フラグをクリア
    
    # ===== 鳴き声区間だけをフレーム分割 =====
    frame_length_sec = processing_params['frame_length_sec']
    hop_length_sec = processing_params['hop_length_sec']
    frame_length = int(sr * frame_length_sec)
    hop_length = int(sr * hop_length_sec)
    
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
    print(f"抽出フレーム数: {len(mfcc_array)}")
    print(f"特徴量 shape: {mfcc_array.shape}")
    
    # ===== クラスタリング =====
    k = 4
    kmeans = KMeans(n_clusters=k, random_state=0)
    labels = kmeans.fit_predict(mfcc_array)

    
    # フィルタリングGUIを起動
    print("\n===== フレームフィルタリング =====")
    print("GUIでフレームをフィルタリングします...")
    gui = FrameFilteringGUI(y, sr, frame_times, mfcc_array, labels, frame_length, processing_params)
    result = gui.run()
    
    # 結果を取得
    keep_flags = result['keep_flags']
    
    # パラメーター再処理リクエストをチェック
    if result['reprocess_requested']:
        # 新しいパラメーターを適用
        processing_params = result['params']
        reprocess = True
        print("\n===== パラメーター変更: 再処理を開始 =====")
        continue  # ループの最初に戻って再処理
    
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
