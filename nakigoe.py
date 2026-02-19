import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import tkinter.font as tkfont
import threading
import time

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd
import soundfile as sf
from sklearn.cluster import KMeans
from umap import UMAP
import scipy.signal as signal
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as patches


# ===== 統合GUI クラス定義 =====
class BirdcallAnalysisGUI:
    def __init__(self):
        # 音声データとパラメーター
        self.file_path = None
        self.y_original = None  # 元の読み込み音声（処理前）
        self.y = None  # フィルタ適用後など（処理後、再生用）
        self.sr = None
        self.frame_times = []
        self.mfcc_array = None
        self.labels = None
        self.frame_length = 0
        self.segments = []

        # パラメーター（初期値）
        self.param_frame_length = 0.2
        self.param_hop_length = 0.2
        self.param_cutoff = 3000
        self.param_top_db = 45

        # フレームを除外するかのフラグ（True=残す, False=除外）
        self.keep_flags = []
        self.current_index = 0
        self.is_playing = False
        self.auto_play_mode = False

        # 処理状態
        self.processing_done = False

        # フォントサイズ管理（初期サイズ）
        self.font_size = 16

        # base window size (for font_size 12)
        self._base_width = 750
        self._base_height = 850

        # spectrogram / playback state
        self.spec_fig = None
        self.spec_ax_pre = None
        self.spec_ax_post = None
        self.canvas = None
        self.rect_patch = None
        self.selection = (0.0, 0.0)  # start_sec, end_sec
        self.play_thread = None
        self.play_stop_event = threading.Event()
        self.is_paused = True

        # repeat control for buttons (hold)
        self._repeat_job = None

        # GUIウィンドウの作成
        self.root = tk.Tk()
        self.root.title("鳥の鳴き声分析ツール")

        # アプリ全体のデフォルトフォントを設定（tkウィジェットに反映）
        try:
            self.root.option_add("*Font", ("Arial", self.font_size))
        except Exception:
            pass

        # ベースフォントを取得して初期サイズを設定（TkDefaultFont を変更して ttk も反映を試みる）
        try:
            self.base_font = tkfont.nametofont("TkDefaultFont")
            self.base_font.configure(size=self.font_size)
        except Exception:
            self.base_font = None

        # ウィンドウ初期サイズをフォントサイズに合わせて計算・設定
        try:
            scale = float(self.font_size) / 12.0
            width = max(400, int(self._base_width * scale))
            height = max(300, int(self._base_height * scale))
            self.root.geometry(f"{width}x{height}")
        except Exception:
            pass

        # ===== ファイル選択エリア =====
        file_frame = ttk.LabelFrame(self.root, text="1. WAVファイル選択", padding="10")
        file_frame.pack(fill=tk.X, padx=10, pady=10)

        self.file_path_var = tk.StringVar(value="（ファイルが選択されていません）")
        file_label = ttk.Label(
            file_frame,
            textvariable=self.file_path_var,
            relief=tk.SUNKEN,
            width=50
        )
        file_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        select_file_btn = ttk.Button(
            file_frame,
            text="ファイルを選択",
            command=self.select_file,
            width=15
        )
        select_file_btn.pack(side=tk.LEFT, padx=5)

        self.process_btn = ttk.Button(
            file_frame,
            text="処理開始",
            command=self.start_processing,
            state=tk.DISABLED,
            width=15
        )
        self.process_btn.pack(side=tk.LEFT, padx=5)

        # ===== パラメーター調整エリア =====
        param_frame = ttk.LabelFrame(self.root, text="2. パラメーター調整", padding="10")
        param_frame.pack(fill=tk.X, padx=10, pady=10)

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
            length=250,
            command=self.update_frame_length
        )
        self.frame_length_slider.set(self.param_frame_length)
        self.frame_length_slider.pack(side=tk.LEFT, padx=5)

        # 説明（簡潔）
        ttk.Label(frame_length_frame, text="説明: 1フレームの長さ（秒）。長いほど時間情報を多く含む。", foreground="gray").pack(side=tk.LEFT, padx=8)

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
            from_=0.05,
            to=0.5,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            length=250,
            command=self.update_hop_length
        )
        self.hop_length_slider.set(self.param_hop_length)
        self.hop_length_slider.pack(side=tk.LEFT, padx=5)

        # 説明（簡潔）
        ttk.Label(hop_length_frame, text="説明: フレーム間の開始間隔。重なりを制御（小さくすると重複増）。", foreground="gray").pack(side=tk.LEFT, padx=8)

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
            length=250,
            command=self.update_cutoff
        )
        self.cutoff_slider.set(self.param_cutoff)
        self.cutoff_slider.pack(side=tk.LEFT, padx=5)

        # 説明（簡潔）
        ttk.Label(cutoff_frame, text="説明: この周波数以上を残す。低周波ノイズ除去に有効。", foreground="gray").pack(side=tk.LEFT, padx=8)

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
            length=250,
            command=self.update_top_db
        )
        self.top_db_slider.set(self.param_top_db)
        self.top_db_slider.pack(side=tk.LEFT, padx=5)

        # 説明（簡潔）
        ttk.Label(top_db_frame, text="説明: 鳴き声区間抽出の閾値（dB）。大きいほど厳しく抽出。", foreground="gray").pack(side=tk.LEFT, padx=8)

        # ===== フレーム情報表示エリア =====
        info_frame = ttk.LabelFrame(self.root, text="3. フレーム情報", padding="10")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # info_label の wraplength はウィンドウ幅に合わせてスケーリング
        try:
            wraplength = int(650 * (float(self.font_size) / 12.0))
        except Exception:
            wraplength = 650

        self.info_label = tk.Label(
            info_frame,
            text="ファイルを選択して処理を開始してください",
            font=("Arial", max(12, int(self.font_size + 2))),
            justify=tk.LEFT,
            wraplength=wraplength
        )
        self.info_label.pack(pady=10)

        self.progress_label = tk.Label(
            info_frame,
            text="",
            font=("Arial", max(10, int(self.font_size))),
            fg="blue"
        )
        self.progress_label.pack(pady=5)

        # ===== WAV選択エリア =====
        audio_frame = ttk.Frame(info_frame)
        audio_frame.pack(fill=tk.X, pady=5)

        ttk.Label(audio_frame, text="再生ソース:").pack(side=tk.LEFT, padx=5)

        self.audio_path_var = tk.StringVar(value="（処理前）")
        audio_label = ttk.Label(
            audio_frame,
            textvariable=self.audio_path_var,
            relief=tk.SUNKEN,
            width=40
        )
        audio_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.select_wav_btn = ttk.Button(
            audio_frame,
            text="別のWAVを選択",
            command=self.select_wav_file,
            width=15,
            state=tk.DISABLED
        )
        self.select_wav_btn.pack(side=tk.LEFT, padx=5)

        # ===== 操作ボタンエリア =====
        button_frame = ttk.Frame(info_frame)
        button_frame.pack(pady=10)

        # ナビゲーションボタン（前へ・次へ）
        nav_frame = ttk.Frame(button_frame)
        nav_frame.grid(row=0, column=0, columnspan=3, pady=5)

        self.prev_btn = ttk.Button(
            nav_frame,
            text="◀ 前へ",
            command=self.play_prev,
            width=15,
            state=tk.DISABLED
        )
        self.prev_btn.grid(row=0, column=0, padx=5)

        self.next_btn = ttk.Button(
            nav_frame,
            text="次へ ▶",
            command=self.play_next,
            width=15,
            state=tk.DISABLED
        )
        self.next_btn.grid(row=0, column=1, padx=5)

        # 再生・除外・保存ボタン
        self.play_btn = ttk.Button(
            button_frame,
            text="▶ 再生",
            command=self.play_current,
            width=15,
            state=tk.DISABLED
        )
        self.play_btn.grid(row=1, column=0, padx=5, pady=5)

        self.exclude_btn = ttk.Button(
            button_frame,
            text="✗ 除外",
            command=self.exclude_current,
            width=15,
            state=tk.DISABLED
        )
        self.exclude_btn.grid(row=1, column=1, padx=5, pady=5)

        self.save_btn = ttk.Button(
            button_frame,
            text="💾 一括保存",
            command=self.save_all_frames,
            width=15,
            state=tk.DISABLED
        )
        self.save_btn.grid(row=1, column=2, padx=5, pady=5)

        # 全再生・完了・停止ボタン
        self.auto_play_btn = ttk.Button(
            button_frame,
            text="▶▶ 全再生",
            command=self.start_auto_play,
            width=15,
            state=tk.DISABLED
        )
        self.auto_play_btn.grid(row=2, column=0, padx=5, pady=5)

        self.finish_btn = ttk.Button(
            button_frame,
            text="✓ 完了",
            command=self.finish_filtering,
            width=15,
            state=tk.DISABLED
        )
        self.finish_btn.grid(row=2, column=1, padx=5, pady=5)

        self.stop_btn = ttk.Button(
            button_frame,
            text="■ 停止",
            command=self.stop_auto_play,
            width=15,
            state=tk.DISABLED
        )
        self.stop_btn.grid(row=2, column=2, padx=5, pady=5)

        # 使い方の説明
        help_text = (
            "使い方：\n"
            "1. WAVファイルを選択して「処理開始」\n"
            "2. 各フレームを「前へ」「次へ」で確認\n"
            "3. 不要なフレームは「除外」\n"
            "4. 「完了」でUMAP可視化へ\n\n"
            "スペクトログラム表示:\n"
            "上: 処理前スペクトログラム（元音声）\n"
            "下: 処理後スペクトログラム（フィルタ・抽出後）\n"
            "パラメーターを変更して「処理開始」を押すと再処理します。"
        )
        help_label = tk.Label(
            info_frame,
            text=help_text,
            font=("Arial", max(9, int(self.font_size - 6))),
            justify=tk.LEFT,
            fg="gray"
        )
        help_label.pack(pady=5)

        # ===== スペクトログラム表示エリア (上下に並べる) =====
        spec_frame = ttk.LabelFrame(self.root, text="4. スペクトログラム (処理前 / 処理後)", padding="6")
        spec_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Matplotlib Figure: 2 行で上下に並べる
        self.spec_fig, (self.spec_ax_pre, self.spec_ax_post) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
        plt.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.spec_fig, master=spec_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # スライダー2つ (start, end) - 選択は「処理後」スペクトログラムに反映
        slider_frame = ttk.Frame(spec_frame)
        slider_frame.pack(fill=tk.X, pady=4)

        ttk.Label(slider_frame, text="開始:").pack(side=tk.LEFT, padx=5)
        self.start_slider = tk.Scale(
            slider_frame, from_=0.0, to=1.0, resolution=0.01, orient=tk.HORIZONTAL,
            length=300, command=self.on_start_slider
        )
        self.start_slider.set(0.0)
        self.start_slider.pack(side=tk.LEFT, padx=5)

        ttk.Label(slider_frame, text="終了:").pack(side=tk.LEFT, padx=5)
        self.end_slider = tk.Scale(
            slider_frame, from_=0.0, to=1.0, resolution=0.01, orient=tk.HORIZONTAL,
            length=300, command=self.on_end_slider
        )
        self.end_slider.set(1.0)
        self.end_slider.pack(side=tk.LEFT, padx=5)

        # 操作ボタン (再生 / 削除)
        spec_button_frame = ttk.Frame(spec_frame)
        spec_button_frame.pack(pady=4)

        self.spec_play_btn = ttk.Button(spec_button_frame, text="▶ Play Selection", command=self.toggle_play_selection, state=tk.DISABLED)
        self.spec_play_btn.grid(row=0, column=0, padx=4)

        self.spec_delete_btn = ttk.Button(spec_button_frame, text="Delete Selection", command=self.delete_selection_frames, state=tk.DISABLED)
        self.spec_delete_btn.grid(row=0, column=1, padx=4)

        # 左右移動ボタン(長押し対応) - 選択範囲を移動
        self.left_btn = ttk.Button(spec_button_frame, text="◀", width=4)
        self.left_btn.grid(row=0, column=2, padx=4)
        self.left_btn.bind("<ButtonPress-1>", lambda e: self.start_repeat(-1))
        self.left_btn.bind("<ButtonRelease-1>", lambda e: self.stop_repeat())

        self.right_btn = ttk.Button(spec_button_frame, text="▶", width=4)
        self.right_btn.grid(row=0, column=3, padx=4)
        self.right_btn.bind("<ButtonPress-1>", lambda e: self.start_repeat(+1))
        self.right_btn.bind("<ButtonRelease-1>", lambda e: self.stop_repeat())

        # キーイベントのバインド
        self.root.bind("<space>", lambda e: self.toggle_play_selection())
        self.root.bind("<Left>", lambda e: self.step_selection(-1))
        self.root.bind("<Right>", lambda e: self.step_selection(+1))
        self.root.bind("<Delete>", lambda e: self.delete_selection_frames())

        # 初期表示を更新
        self.apply_font_size()

    def select_file(self):
        """メインのWAVファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="WAVファイルを選択してください",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
        )

        if file_path:
            self.file_path = file_path
            self.file_path_var.set(os.path.basename(file_path))
            self.process_btn.config(state=tk.NORMAL)
            print(f"選択されたファイル: {file_path}")

    def start_processing(self):
        """音声処理を開始（再処理も可能）"""
        if not self.file_path:
            messagebox.showerror("エラー", "ファイルが選択されていません")
            return

        # ボタンを無効化
        self.process_btn.config(state=tk.DISABLED)
        self.info_label.config(text="処理中...")

        # 別スレッドで処理を実行（再処理をサポート）
        thread = threading.Thread(target=self.process_audio, daemon=True)
        thread.start()

    def process_audio(self):
        """音声処理のメイン処理"""
        try:
            # 出力ディレクトリの作成
            output_dir = "cluster_segments"
            os.makedirs(output_dir, exist_ok=True)

            # ===== 音声読み込み =====
            # 常に元音声を保存（再処理時は上書き）
            y_original, sr = librosa.load(self.file_path, sr=None)
            self.y_original = y_original
            print(f"\n録音時間: {len(y_original) / sr:.2f} 秒")

            # ===== 高周波だけを残すハイパスフィルタ =====
            cutoff = self.param_cutoff
            b, a = signal.butter(4, cutoff / (sr / 2), btype="high")
            y = signal.filtfilt(b, a, y_original)
            print(f"ハイパスフィルタ適用完了（{cutoff}Hz以上を抽出）")
            self.y = y
            self.sr = sr

            # ===== 鳴き声のある区間だけを抽出 =====
            top_db = self.param_top_db
            intervals = librosa.effects.split(y, top_db=top_db)

            segments = []
            for start, end in intervals:
                duration = (end - start) / sr
                if duration >= 0.1:  # 0.1秒以上の音だけ採用
                    segments.append((start, end))

            print(f"抽出された鳴き声区間: {len(segments)}")
            self.segments = segments

            # ===== スペクトログラムデータ（処理前・処理後） =====
            n_fft = 2048
            hop = 512

            D_pre = np.abs(librosa.stft(y_original, n_fft=n_fft, hop_length=hop))
            D_db_pre = librosa.amplitude_to_db(D_pre, ref=np.max)

            D_post = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop))
            D_db_post = librosa.amplitude_to_db(D_post, ref=np.max)

            times = librosa.frames_to_time(np.arange(D_db_post.shape[1]), sr=sr, hop_length=hop)
            freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

            # ===== 鳴き声区間だけをフレーム分割 =====
            frame_length_sec = self.param_frame_length
            hop_length_sec = self.param_hop_length
            frame_length = int(sr * frame_length_sec)
            hop_length = int(sr * hop_length_sec)

            mfcc_list = []
            frame_times = []

            for start, end in segments:
                segment = y[start:end]

                for i in range(0, len(segment), hop_length):
                    frame = segment[i: i + frame_length]
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
            if len(mfcc_array) == 0:
                labels = np.array([], dtype=int)
            else:
                k = 4
                kmeans = KMeans(n_clusters=k, random_state=0)
                labels = kmeans.fit_predict(mfcc_array)

            # データを保存（上書きして再処理に対応）
            self.frame_times = frame_times
            self.mfcc_array = mfcc_array
            self.labels = labels
            self.frame_length = frame_length
            self.keep_flags = [True] * len(frame_times)
            self.current_index = 0
            self.processing_done = True

            # reset selection to full duration (処理後音声の長さ)
            duration = len(self.y) / float(self.sr)
            self.selection = (0.0, duration)

            # GUIを更新（メインスレッドで実行） - スペクトログラム描画含む
            self.root.after(0, lambda: self.enable_filtering_ui_and_draw(D_db_pre, D_db_post, times, freqs))

        except Exception as e:
            print(f"処理エラー: {e}")
            self.root.after(0, lambda: messagebox.showerror("処理エラー", f"処理中にエラーが発生しました：\n{e}"))
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))

    def enable_filtering_ui_and_draw(self, D_db_pre, D_db_post, times, freqs):
        """フィルタリングUIを有効化し、スペクトログラム（上: 処理前 / 下: 処理後）を表示"""
        self.enable_filtering_ui()

        try:
            # clear axes
            self.spec_ax_pre.clear()
            self.spec_ax_post.clear()

            # Draw pre-processing spectrogram (always available after loading)
            if D_db_pre is not None:
                librosa.display.specshow(D_db_pre, sr=self.sr, hop_length=512, x_axis="time", y_axis="hz", ax=self.spec_ax_pre)
                self.spec_ax_pre.set_title("Spectrogram (Before Processing)")
            else:
                self.spec_ax_pre.set_title("Spectrogram (Before Processing) - no data")

            # Draw post-processing spectrogram (available after processing)
            if D_db_post is not None:
                librosa.display.specshow(D_db_post, sr=self.sr, hop_length=512, x_axis="time", y_axis="hz", ax=self.spec_ax_post)
                self.spec_ax_post.set_title("Spectrogram (After Processing)")
            else:
                self.spec_ax_post.set_title("Spectrogram (After Processing) - no data")

            self.spec_fig.tight_layout()
            self.canvas.draw_idle()
        except Exception as e:
            print(f"スペクトログラム描画エラー: {e}")

        # set sliders ranges to audio duration (use processed audio length if available, otherwise original)
        duration = 0.0
        if self.y is not None and self.sr is not None:
            duration = len(self.y) / float(self.sr)
        elif self.y_original is not None and self.sr is not None:
            duration = len(self.y_original) / float(self.sr)

        if duration <= 0:
            duration = 1.0

        self.start_slider.config(from_=0.0, to=duration, resolution=max(0.01, duration / 1000.0))
        self.end_slider.config(from_=0.0, to=duration, resolution=max(0.01, duration / 1000.0))
        self.start_slider.set(0.0)
        self.end_slider.set(round(duration, 3))
        self.selection = (0.0, duration)
        self._draw_selection_rect()

        # Enable or disable spec controls depending on whether processed audio exists
        if self.processing_done and D_db_post is not None:
            self.spec_play_btn.config(state=tk.NORMAL)
            self.spec_delete_btn.config(state=tk.NORMAL)
        else:
            self.spec_play_btn.config(state=tk.DISABLED)
            self.spec_delete_btn.config(state=tk.DISABLED)

    def enable_filtering_ui(self):
        """フィルタリングUIを有効化"""
        if self.file_path:
            self.audio_path_var.set(f"{os.path.basename(self.file_path)}")
        self.select_wav_btn.config(state=tk.NORMAL)
        self.prev_btn.config(state=tk.NORMAL)
        self.next_btn.config(state=tk.NORMAL)
        self.play_btn.config(state=tk.NORMAL)
        self.exclude_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL)
        self.auto_play_btn.config(state=tk.NORMAL)
        self.finish_btn.config(state=tk.NORMAL)
        self.process_btn.config(state=tk.NORMAL)  # 再処理可能にする
        self.update_info()

    def select_wav_file(self):
        """再生用の別のWAVファイルを選択（処理前のスペクトログラム更新）"""
        file_path = filedialog.askopenfilename(
            title="WAVファイルを選択してください",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            y_new, sr_new = librosa.load(file_path, sr=None)
            self.y_original = y_new
            self.y = y_new  # playback will use this until processing
            self.sr = sr_new
            self.frame_length = int(self.param_frame_length * self.sr)
            duration = librosa.get_duration(y=self.y, sr=self.sr)
            display_text = f"{os.path.basename(file_path)} ({duration:.2f}s, {self.sr}Hz)"
            self.audio_path_var.set(display_text)
            messagebox.showinfo("読み込み完了", f"WAVファイルを読み込みました：\n{display_text}")

            # Update pre-processing spectrogram for newly loaded wav (post remains as-is until processing)
            D = np.abs(librosa.stft(self.y_original, n_fft=2048, hop_length=512))
            D_db = librosa.amplitude_to_db(D, ref=np.max)
            # If no processed data yet, pass None for post
            post = None
            if self.processing_done and self.y is not None and self.y is not self.y_original:
                # if processing was done and y differs, compute post spectrogram
                Dp = np.abs(librosa.stft(self.y, n_fft=2048, hop_length=512))
                post = librosa.amplitude_to_db(Dp, ref=np.max)
            self.enable_filtering_ui_and_draw(D_db, post, None, None)
        except Exception as e:
            messagebox.showerror("読み込みエラー", f"WAVファイルの読み込みに失敗しました：\n{e}")

    def apply_font_size(self):
        """設定したフォントサイズを主要ウィジェットに適用する"""
        try:
            # TkDefaultFont を更新（ttk も反映する場合がある）
            if self.base_font is not None:
                self.base_font.configure(size=self.font_size)
        except Exception:
            pass

        try:
            # tkinter ウィジェット向けにデフォルトフォントを再設定
            self.root.option_add("*Font", ("Arial", self.font_size))
        except Exception:
            pass

        try:
            # 情報表示系はやや大きめに
            self.info_label.config(font=("Arial", max(12, int(self.font_size + 2))))
            self.progress_label.config(font=("Arial", max(10, int(self.font_size))))
            # wraplength も更新してウィンドウ幅に合わせる
            wraplength = int(650 * (float(self.font_size) / 12.0))
            self.info_label.config(wraplength=wraplength)
        except Exception:
            pass

    def update_frame_length(self, value):
        """フレーム長パラメーターを更新"""
        self.param_frame_length = float(value)
        self.frame_length_value_label.config(text=f"{self.param_frame_length:.2f} 秒")
        if self.sr:
            self.frame_length = int(self.param_frame_length * self.sr)

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

    def update_info(self):
        """現在のフレーム情報を更新"""
        if not self.processing_done:
            return

        if self.current_index >= len(self.frame_times):
            self.info_label.config(
                text="すべてのフレームを確認しました。\n「完了」をクリックしてください。"
            )
            self.play_btn.config(state=tk.DISABLED)
            self.exclude_btn.config(state=tk.DISABLED)
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)
            self.auto_play_btn.config(state=tk.DISABLED)
            return

        frame_time = self.frame_times[self.current_index]
        cluster = self.labels[self.current_index] if self.labels is not None and len(self.labels) > self.current_index else "N/A"
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
        if not self.processing_done or self.current_index >= len(self.frame_times):
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

                sd.play(frame_audio, self.sr)
                sd.wait()
            except Exception as e:
                print(f"再生エラー: {e}")
            finally:
                self.is_playing = False
                self.root.after(0, lambda: self.play_btn.config(state=tk.NORMAL))
                self.root.after(0, self.update_info)

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
        if not self.processing_done or self.current_index >= len(self.frame_times):
            return

        self.keep_flags[self.current_index] = False
        self.update_info()

    def save_all_frames(self):
        """除外していないすべてのフレームを一括保存"""
        frames_to_save = [i for i, keep in enumerate(self.keep_flags) if keep]

        if not frames_to_save:
            messagebox.showwarning("警告", "保存するフレームがありません。すべて除外されています。")
            return

        save_dir = filedialog.askdirectory(
            title="保存先ディレクトリを選択してください",
            initialdir=os.getcwd()
        )

        if not save_dir:
            return

        try:
            saved_count = 0
            for i in frames_to_save:
                frame_time = self.frame_times[i]
                start_sample = int(frame_time * self.sr)
                end_sample = min(start_sample + self.frame_length, len(self.y))
                frame_audio = self.y[start_sample:end_sample]

                file_name = f"frame_{i}_{self.labels[i] if self.labels is not None and len(self.labels)>i else 'na'}.wav"
                file_path = os.path.join(save_dir, file_name)

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

                    self.root.after(0, self.update_info)

                    sd.play(frame_audio, self.sr)
                    sd.wait()

                    self.current_index += 1
            except Exception as e:
                print(f"自動再生エラー: {e}")
            finally:
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
        self.prev_btn.config(state=tk.NORMAL)
        self.next_btn.config(state=tk.NORMAL)
        self.update_info()

    def finish_filtering(self):
        """フィルタリングを完了してUMAP可視化へ"""
        if not self.processing_done:
            messagebox.showwarning("警告", "処理が完了していません")
            return

        # フィルタリング結果を適用
        filtered_indices = [i for i in range(len(self.keep_flags)) if self.keep_flags[i]]
        frame_times = [self.frame_times[i] for i in filtered_indices]
        mfcc_array = self.mfcc_array[filtered_indices]
        labels = self.labels[filtered_indices]

        print(f"フィルタリング完了: {len(filtered_indices)} / {len(self.keep_flags)} フレームを保持")

        # 出力ディレクトリ
        output_dir = "cluster_segments"

        # UMAP 可視化
        umap = UMAP(n_components=2, random_state=0)
        points = umap.fit_transform(mfcc_array)

        plt.figure(figsize=(8, 6))
        plt.scatter(points[:, 0], points[:, 1], c=labels, cmap="tab10")
        plt.title("Bird Call Clustering (UMAP)")
        plt.xlabel("UMAP Dimension 1")
        plt.ylabel("UMAP Dimension 2")

        umap_path = os.path.join(output_dir, "cluster_visualization_umap.png")
        plt.savefig(umap_path, dpi=150, bbox_inches="tight")
        print(f"UMAP可視化を保存しました: {umap_path}")
        plt.show()

        # クラスタごとの代表鳴き声を保存
        num_samples = 10
        k = len(set(labels))

        for c in range(k):
            idx_list = [i for i in range(len(labels)) if labels[i] == c]

            if len(idx_list) == 0:
                print(f"クラスタ {c} にはフレームがありません")
                continue

            print(f"クラスタ {c}: {len(idx_list)} 個のフレームから {num_samples} 個の区間を保存")

            used_segments = set()
            count = 0

            for idx in idx_list:
                if count >= num_samples:
                    break

                frame_time = frame_times[idx]

                for seg_i, (start, end) in enumerate(self.segments):
                    if start / self.sr <= frame_time <= end / self.sr:
                        if seg_i in used_segments:
                            break

                        used_segments.add(seg_i)
                        count += 1

                        segment_audio = self.y[start:end]
                        out_path = f"{output_dir}/cluster_{c}_seg{seg_i}.wav"
                        sf.write(out_path, segment_audio, self.sr)

                        print(f"  → 区間 {seg_i} を保存: {out_path}")
                        break

        # クラスタごとのスペクトログラム表示
        plt.figure(figsize=(20, 10))
        plot_index = 1

        for c in range(k):
            idx_list = [i for i in range(len(labels)) if labels[i] == c]
            if len(idx_list) == 0:
                continue

            for n, idx in enumerate(idx_list[:num_samples]):
                start_time = frame_times[idx]
                start_sample = int(start_time * self.sr)
                end_sample = start_sample + self.frame_length
                sample = self.y[start_sample:end_sample]

                D = librosa.amplitude_to_db(
                    np.abs(librosa.stft(sample, n_fft=1024, hop_length=256)), ref=np.max
                )

                plt.subplot(k, num_samples, plot_index)
                librosa.display.specshow(D, sr=self.sr, x_axis="time", y_axis="hz")
                plt.title(f"C{c}-{n}")
                plot_index += 1

        plt.tight_layout()
        spectrograms_path = os.path.join(output_dir, "cluster_spectrograms.png")
        plt.savefig(spectrograms_path, dpi=150, bbox_inches="tight")
        print(f"クラスタスペクトログラムを保存しました: {spectrograms_path}")
        plt.show()

        # クラスタごとの時間帯を表示
        for c in range(k):
            print(f"\nクラスタ {c}:")
            times = [frame_times[i] for i in range(len(labels)) if labels[i] == c]
            print(times[:100])

        messagebox.showinfo("完了", "すべての処理が完了しました！")

    # ---------------------------
    # Spectrogram / Selection helpers
    # ---------------------------
    def _draw_selection_rect(self):
        """処理後スペクトログラム上に選択範囲を描画（濃く）"""
        if self.spec_ax_post is None:
            return
        # remove previous patch
        if self.rect_patch is not None:
            try:
                self.rect_patch.remove()
            except Exception:
                pass
            self.rect_patch = None

        start_sec, end_sec = self.selection
        if end_sec <= start_sec:
            # still update canvas to remove previous
            try:
                self.canvas.draw_idle()
            except Exception:
                pass
            return

        ylim = self.spec_ax_post.get_ylim()
        height = ylim[1] - ylim[0]
        # create a rectangle spanning the selection time along x, covering whole y
        rect = patches.Rectangle((start_sec, ylim[0]), end_sec - start_sec, height,
                                 linewidth=0, facecolor='black', alpha=0.25, zorder=10)
        self.rect_patch = rect
        try:
            self.spec_ax_post.add_patch(self.rect_patch)
            self.canvas.draw_idle()
        except Exception as e:
            print(f"選択矩形描画エラー: {e}")

    def on_start_slider(self, v):
        try:
            s = float(v)
            _, e = self.selection
            if s >= e:
                # keep at most slightly less than end
                s = max(0.0, e - 0.001)
                self.start_slider.set(s)
            self.selection = (s, e)
            self._draw_selection_rect()
        except Exception:
            pass

    def on_end_slider(self, v):
        try:
            e = float(v)
            s, _ = self.selection
            if e <= s:
                e = min(len(self.y) / float(self.sr) if self.y is not None else (len(self.y_original) / float(self.sr) if self.y_original is not None else 1.0), s + 0.001)
                self.end_slider.set(e)
            self.selection = (s, e)
            self._draw_selection_rect()
        except Exception:
            pass

    def toggle_play_selection(self):
        """スペースまたはボタンで選択範囲の再生/停止（処理後音声に対して動作）"""
        if self.y is None or self.sr is None:
            return

        if self.play_thread and self.play_thread.is_alive():
            # stop current play
            self.play_stop_event.set()
            sd.stop()
            return

        # start playback of selection in a thread
        start_sec, end_sec = self.selection
        if end_sec <= start_sec:
            return

        start_sample = int(start_sec * self.sr)
        end_sample = int(end_sec * self.sr)
        audio = self.y[start_sample:end_sample]

        def _play():
            self.play_stop_event.clear()
            try:
                sd.play(audio, self.sr)
                # wait while checking for stop event
                while sd.get_stream() is not None and sd.get_stream().active:
                    if self.play_stop_event.is_set():
                        sd.stop()
                        break
                    time.sleep(0.05)
            except Exception as e:
                print(f"再生エラー: {e}")
            finally:
                self.play_stop_event.set()

        self.play_thread = threading.Thread(target=_play, daemon=True)
        self.play_thread.start()

    def step_selection(self, direction):
        """矢印キーで選択範囲をフレーム単位で移動（direction: -1 left, +1 right）"""
        if self.y is None or self.sr is None:
            # if no processed audio, attempt to use original
            if self.y_original is None or self.sr is None:
                return
        hop = max(0.01, self.param_hop_length)  # seconds
        s, e = self.selection
        dur = len(self.y) / float(self.sr) if self.y is not None else len(self.y_original) / float(self.sr)
        s = max(0.0, min(dur, s + direction * hop))
        e = max(0.0, min(dur, e + direction * hop))
        if e <= s:
            # ensure a minimal window length
            e = min(dur, s + 0.01)
        self.selection = (s, e)
        self.start_slider.set(s)
        self.end_slider.set(e)
        self._draw_selection_rect()

    def start_repeat(self, direction):
        """ボタンの長押しで連続移動を開始"""
        self.stop_repeat()
        self._repeat_step(direction)
        # schedule repeated calls
        self._repeat_job = self.root.after(150, lambda: self._repeat_loop(direction))

    def _repeat_loop(self, direction):
        self._repeat_step(direction)
        self._repeat_job = self.root.after(80, lambda: self._repeat_loop(direction))

    def _repeat_step(self, direction):
        self.step_selection(direction)

    def stop_repeat(self):
        if self._repeat_job is not None:
            try:
                self.root.after_cancel(self._repeat_job)
            except Exception:
                pass
            self._repeat_job = None

    def delete_selection_frames(self):
        """選択範囲内にあるフレームを除外（keep_flags を False にする）"""
        if not self.processing_done:
            messagebox.showwarning("警告", "先に処理を行ってください")
            return
        s, e = self.selection
        removed = 0
        for i, t in enumerate(self.frame_times):
            if s <= t <= e and self.keep_flags[i]:
                self.keep_flags[i] = False
                removed += 1
        messagebox.showinfo("削除", f"{removed} 個のフレームを除外しました")
        self.update_info()

    def run(self):
        """GUIを表示して実行"""
        self.root.mainloop()


# ===== メイン処理 =====
if __name__ == "__main__":
    app = BirdcallAnalysisGUI()
    app.run()
