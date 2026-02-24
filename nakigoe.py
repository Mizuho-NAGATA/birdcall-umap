import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import tkinter.font as tkfont
import threading

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd
import soundfile as sf
from matplotlib.widgets import Button
from sklearn.cluster import KMeans
from umap import UMAP
import scipy.signal as signal


# ===== 統合GUI クラス定義 =====
class BirdcallAnalysisGUI:
    def __init__(self):
        # 音声データとパラメーター
        self.file_path = None
        self.y = None
        self.sr = None
        self.frame_times = []
        self.mfcc_array = None
        self.labels = None
        self.frame_length = 0
        self.segments = []
        
        # パラメーター（初期値）
        self.param_frame_length = 0.25
        self.param_hop_length = 0.25
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
        # ここを変更するとウィンドウの初期サイズも自動で変わります（例: 18 や 20 も可）
        self.font_size = 16
        
        # base window size (for font_size 12)
        self._base_width = 750
        self._base_height = 850

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
            from_=0.1,
            to=0.5,
            resolution=0.05,
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
            "4. 「完了」でUMAP可視化へ"
        )
        help_label = tk.Label(
            info_frame,
            text=help_text,
            font=("Arial", max(9, int(self.font_size - 6))),
            justify=tk.LEFT,
            fg="gray"
        )
        help_label.pack(pady=5)
        
        # 初期表示を更新
        self.apply_font_size()
        
    def get_output_dir(self):
        """
        出力先フォルダを返す。
        既定: 選択した WAV ファイルと同じフォルダ配下に cluster_segments を作る。
        （カレントディレクトリに書き込めない環境でも動きやすい）
        """
        base_dir = os.path.dirname(self.file_path) if self.file_path else os.getcwd()
        output_dir = os.path.join(base_dir, "cluster_segments")

        try:
            os.makedirs(output_dir, exist_ok=True)
        except PermissionError as e:
            # どこに作ろうとして失敗したかを明示
            messagebox.showerror(
                "アクセスエラー",
                f"出力フォルダを作成できませんでした。\n\n"
                f"出力先: {output_dir}\n"
                f"エラー: {e}\n\n"
                f"対処: 書き込み可能な場所（例: ドキュメント配下）にWAVを置く／管理者権限で実行する等を試してください。"
            )
            raise

        return output_dir    

    
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
        """音声処理を開始"""
        if not self.file_path:
            messagebox.showerror("エラー", "ファイルが選択されていません")
            return
        
        # ボタンを無効化
        self.process_btn.config(state=tk.DISABLED)
        self.info_label.config(text="処理中...")
        
        # 別スレッドで処理を実行
        thread = threading.Thread(target=self.process_audio, daemon=True)
        thread.start()
    
    def process_audio(self):
        """音声処理のメイン処理"""
        try:
            # 出力ディレクトリの作成（WAVと同じフォルダ配下）
            output_dir = self.get_output_dir()
            
            # ===== 音声読み込み =====
            y_original, sr = librosa.load(self.file_path, sr=None)
            print(f"\n録音時間: {len(y_original) / sr:.2f} 秒")
            
            # ===== 高周波だけを残すハイパスフィルタ =====
            cutoff = self.param_cutoff
            b, a = signal.butter(4, cutoff / (sr / 2), btype="high")
            y = signal.filtfilt(b, a, y_original)
            print(f"ハイパスフィルタ適用完了（{cutoff}Hz以上を抽出）")
            
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
            
            # ===== スペクトログラム表示 =====
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
            frame_length_sec = self.param_frame_length
            hop_length_sec = self.param_hop_length
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
            
            # データを保存
            self.y = y
            self.sr = sr
            self.frame_times = frame_times
            self.mfcc_array = mfcc_array
            self.labels = labels
            self.frame_length = frame_length
            self.keep_flags = [True] * len(frame_times)
            self.current_index = 0
            self.processing_done = True
            
            # GUIを更新（メインスレッドで実行）
            self.root.after(0, self.enable_filtering_ui)
            
        except Exception as e:
            print(f"処理エラー: {e}")
            self.root.after(0, lambda: messagebox.showerror("処理エラー", f"処理中にエラーが発生しました：\n{e}"))
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
    
    def enable_filtering_ui(self):
        """フィルタリングUIを有効化"""
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
        """再生用の別のWAVファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="WAVファイルを選択してください",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            y_new, sr_new = librosa.load(file_path, sr=None)
            self.y = y_new
            self.sr = sr_new
            self.frame_length = int(self.param_frame_length * self.sr)
            duration = librosa.get_duration(y=self.y, sr=self.sr)
            display_text = f"{os.path.basename(file_path)} ({duration:.2f}s, {self.sr}Hz)"
            self.audio_path_var.set(display_text)
            messagebox.showinfo("読み込み完了", f"WAVファイルを読み込みました：\n{display_text}")
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
                
                file_name = f"frame_{i}_{self.labels[i]}.wav"
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
        
        # 出力ディレクトリ（WAVと同じフォルダ配下）
        output_dir = self.get_output_dir()
        
        # UMAP 可視化（インタラクティブ）
        umap = UMAP(n_components=2, random_state=0)
        points = umap.fit_transform(mfcc_array)
        labels_array = np.array(labels)
        unique_labels = sorted(set(labels_array))
        marker_options = ["o", "^", "s", "P", "X", "D", "*", "v", "<", ">"]
        cmap = plt.get_cmap("tab10")
        fig, ax = plt.subplots(figsize=(8, 6))
        fig.subplots_adjust(bottom=0.2)
        base_size = 70.0
        cluster_plots = {}
        index_lookup = {}
        
        for idx, label_id in enumerate(unique_labels):
            mask = labels_array == label_id
            base_sizes = np.full(np.sum(mask), base_size, dtype=float)
            color = cmap(idx % cmap.N)
            marker = marker_options[idx % len(marker_options)]
            scatter = ax.scatter(
                points[mask, 0],
                points[mask, 1],
                c=[color],
                marker=marker,
                s=base_sizes,
                label=f"Cluster {label_id}"
            )
            indices = np.nonzero(mask)[0].tolist()
            cluster_plots[label_id] = {
                "scatter": scatter,
                "base_sizes": base_sizes,
                "indices": indices,
            }
            for local_idx, global_idx in enumerate(indices):
                index_lookup[global_idx] = (label_id, local_idx)
        
        ax.set_title("Bird Call Clustering (UMAP)")
        ax.set_xlabel("UMAP Dimension 1")
        ax.set_ylabel("UMAP Dimension 2")
        ax.legend()
        
        playback_state = {"playing": False}
        
        def reset_sizes():
            for data in cluster_plots.values():
                data["scatter"].set_sizes(data["base_sizes"])
            fig.canvas.draw_idle()
        
        def animate_bloom(label_id, local_idx):
            data = cluster_plots[label_id]
            sizes = data["base_sizes"].copy()
            sizes[local_idx] = sizes[local_idx] * 3.0
            data["scatter"].set_sizes(sizes)
            fig.canvas.draw_idle()
        
        def restore_bloom(label_id):
            data = cluster_plots[label_id]
            data["scatter"].set_sizes(data["base_sizes"])
            fig.canvas.draw_idle()
        
        def play_sequence(event):
            if playback_state["playing"]:
                return
            
            playback_state["playing"] = True
            
            def worker():
                try:
                    for global_idx, frame_time in enumerate(frame_times):
                        start_sample = int(frame_time * self.sr)
                        end_sample = min(start_sample + self.frame_length, len(self.y))
                        frame_audio = self.y[start_sample:end_sample]
                        label_local = index_lookup.get(global_idx)
                        
                        if label_local is not None:
                            label_id, local_idx = label_local
                            animate_bloom(label_id, local_idx)
                        
                        sd.play(frame_audio, self.sr)
                        sd.wait()
                        
                        if label_local is not None:
                            restore_bloom(label_id)
                    
                    reset_sizes()
                except Exception as e:
                    print(f"再生中のエラー: {e}")
                finally:
                    playback_state["playing"] = False
            
            threading.Thread(target=worker, daemon=True).start()
        
        play_ax = fig.add_axes([0.72, 0.05, 0.2, 0.08])
        play_button = Button(play_ax, "再生", color="lightgoldenrodyellow", hovercolor="0.95")
        play_button.on_clicked(play_sequence)
        
        umap_path = os.path.join(output_dir, "cluster_visualization_umap.png")
        fig.savefig(umap_path, dpi=150, bbox_inches="tight")
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
    
    def run(self):
        """GUIを表示して実行"""
        self.root.mainloop()


# ===== メイン処理 =====
if __name__ == "__main__":
    app = BirdcallAnalysisGUI()
    app.run()



