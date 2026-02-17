import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import numpy as np
import librosa
import scipy.signal as signal
import sounddevice as sd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import threading

class AudioPreprocessingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bird Call Preprocessing - Audio Processing GUI")
        self.root.geometry("1200x800")
        
        # Audio data
        self.y_original = None
        self.y_processed = None
        self.sr = None
        self.file_path = None
        self.segments = []
        self.filtered_segments = []
        
        # Processing parameters
        self.params = {
            'cutoff_freq': tk.IntVar(value=3000),
            'top_db': tk.IntVar(value=45),
            'min_duration': tk.DoubleVar(value=0.1),
            'min_spectral_centroid': tk.IntVar(value=2500),
            'min_zcr': tk.DoubleVar(value=0.1),
            'min_rms': tk.DoubleVar(value=0.005),
            'min_spectral_rolloff': tk.IntVar(value=3500),
            'min_frame_amplitude': tk.DoubleVar(value=0.01),
            'min_frame_energy': tk.DoubleVar(value=0.0001),
            'min_frame_zcr': tk.DoubleVar(value=0.05),
        }
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # File selection section
        file_frame = ttk.LabelFrame(main_frame, text="ファイル選択", padding="5")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.file_label = ttk.Label(file_frame, text="ファイルが選択されていません")
        self.file_label.grid(row=0, column=0, padx=5)
        
        ttk.Button(file_frame, text="WAVファイルを選択", command=self.load_file).grid(row=0, column=1, padx=5)
        
        # Parameters section
        param_frame = ttk.LabelFrame(main_frame, text="前処理パラメータ", padding="5")
        param_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=5)
        
        # Parameter controls
        row = 0
        ttk.Label(param_frame, text="ハイパスフィルタ (Hz):").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, textvariable=self.params['cutoff_freq'], width=10).grid(row=row, column=1, pady=2)
        
        row += 1
        ttk.Label(param_frame, text="音声検出閾値 (top_db):").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, textvariable=self.params['top_db'], width=10).grid(row=row, column=1, pady=2)
        
        row += 1
        ttk.Label(param_frame, text="最小音声長 (秒):").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, textvariable=self.params['min_duration'], width=10).grid(row=row, column=1, pady=2)
        
        row += 1
        ttk.Label(param_frame, text="スペクトル重心 (Hz):").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, textvariable=self.params['min_spectral_centroid'], width=10).grid(row=row, column=1, pady=2)
        
        row += 1
        ttk.Label(param_frame, text="ゼロ交差率:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, textvariable=self.params['min_zcr'], width=10).grid(row=row, column=1, pady=2)
        
        row += 1
        ttk.Label(param_frame, text="RMSエネルギー:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, textvariable=self.params['min_rms'], width=10).grid(row=row, column=1, pady=2)
        
        row += 1
        ttk.Label(param_frame, text="スペクトルロールオフ (Hz):").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(param_frame, textvariable=self.params['min_spectral_rolloff'], width=10).grid(row=row, column=1, pady=2)
        
        # Action buttons
        button_frame = ttk.Frame(param_frame)
        button_frame.grid(row=row+1, column=0, columnspan=2, pady=10)
        
        self.process_btn = ttk.Button(button_frame, text="音声を処理", command=self.process_audio, state=tk.DISABLED)
        self.process_btn.grid(row=0, column=0, padx=5)
        
        self.play_btn = ttk.Button(button_frame, text="処理後の音声を再生", command=self.play_processed, state=tk.DISABLED)
        self.play_btn.grid(row=0, column=1, padx=5)
        
        self.visualize_btn = ttk.Button(button_frame, text="可視化を開始", command=self.start_visualization, state=tk.DISABLED)
        self.visualize_btn.grid(row=0, column=2, padx=5)
        
        # Status section
        status_frame = ttk.LabelFrame(main_frame, text="処理状況", padding="5")
        status_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=5)
        
        self.status_text = tk.Text(status_frame, height=15, width=40, wrap=tk.WORD)
        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.status_text['yscrollcommand'] = scrollbar.set
        
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)
        
        # Visualization section
        viz_frame = ttk.LabelFrame(main_frame, text="波形表示", padding="5")
        viz_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.fig = Figure(figsize=(12, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=viz_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def log_status(self, message):
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.root.update()
        
    def load_file(self):
        file_path = filedialog.askopenfilename(
            title="WAVファイルを選択してください",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            self.log_status(f"ファイルを読み込んでいます: {os.path.basename(file_path)}")
            self.y_original, self.sr = librosa.load(file_path, sr=None)
            self.file_path = file_path
            self.file_label.config(text=os.path.basename(file_path))
            
            duration = len(self.y_original) / self.sr
            self.log_status(f"読み込み完了: {duration:.2f}秒")
            
            # Display original waveform
            self.display_waveform(self.y_original, "元の音声")
            
            # Enable process button
            self.process_btn.config(state=tk.NORMAL)
            
        except Exception as e:
            messagebox.showerror("エラー", f"ファイルの読み込みに失敗しました: {str(e)}")
            self.log_status(f"エラー: {str(e)}")
            
    def display_waveform(self, y, title="波形", segments=None):
        self.ax.clear()
        
        # Time axis
        times = np.arange(len(y)) / self.sr
        
        # Plot waveform
        self.ax.plot(times, y, linewidth=0.5, alpha=0.7, color='gray', label='カットされた部分')
        
        # Highlight kept segments
        if segments:
            for start, end in segments:
                segment_times = times[start:end]
                segment_y = y[start:end]
                self.ax.plot(segment_times, segment_y, linewidth=0.5, color='blue', label='残された部分' if start == segments[0][0] else '')
        
        self.ax.set_xlabel('時間 (秒)')
        self.ax.set_ylabel('振幅')
        self.ax.set_title(title)
        if segments:
            self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        
        self.fig.tight_layout()
        self.canvas.draw()
        
    def process_audio(self):
        if self.y_original is None:
            messagebox.showwarning("警告", "音声ファイルを選択してください")
            return
            
        try:
            self.log_status("\n" + "="*50)
            self.log_status("音声処理を開始します...")
            
            # High-pass filter
            cutoff = self.params['cutoff_freq'].get()
            self.log_status(f"ハイパスフィルタを適用中 ({cutoff}Hz以上)...")
            b, a = signal.butter(4, cutoff / (self.sr / 2), btype="high")
            y = signal.filtfilt(b, a, self.y_original)
            
            # Detect sound intervals
            top_db = self.params['top_db'].get()
            self.log_status(f"音声区間を検出中 (top_db={top_db})...")
            intervals = librosa.effects.split(y, top_db=top_db)
            
            # Filter by duration
            min_duration = self.params['min_duration'].get()
            segments = []
            for start, end in intervals:
                duration = (end - start) / self.sr
                if duration >= min_duration:
                    segments.append((start, end))
            
            self.log_status(f"初期検出: {len(segments)}区間")
            
            # Filter non-bird sounds
            self.log_status("非鳥類音声をフィルタリング中...")
            filtered_segments = []
            for start, end in segments:
                segment = y[start:end]
                
                # Calculate features
                zcr = librosa.feature.zero_crossing_rate(segment)[0]
                zcr_mean = np.mean(zcr)
                
                spectral_centroids = librosa.feature.spectral_centroid(y=segment, sr=self.sr)[0]
                spectral_centroid_mean = np.mean(spectral_centroids)
                
                spectral_rolloff = librosa.feature.spectral_rolloff(y=segment, sr=self.sr, roll_percent=0.85)[0]
                spectral_rolloff_mean = np.mean(spectral_rolloff)
                
                rms = librosa.feature.rms(y=segment)[0]
                rms_mean = np.mean(rms)
                
                # Filter criteria
                is_bird_sound = True
                
                if spectral_centroid_mean < self.params['min_spectral_centroid'].get():
                    is_bird_sound = False
                
                if zcr_mean < self.params['min_zcr'].get():
                    is_bird_sound = False
                
                if rms_mean < self.params['min_rms'].get():
                    is_bird_sound = False
                
                if spectral_rolloff_mean < self.params['min_spectral_rolloff'].get():
                    is_bird_sound = False
                
                if is_bird_sound:
                    filtered_segments.append((start, end))
            
            self.segments = segments
            self.filtered_segments = filtered_segments
            
            self.log_status(f"フィルタリング後: {len(filtered_segments)}区間")
            
            # Create processed audio
            self.y_processed = np.zeros_like(y)
            for start, end in filtered_segments:
                self.y_processed[start:end] = y[start:end]
            
            # Calculate statistics
            total_duration = len(y) / self.sr
            kept_duration = sum((end - start) for start, end in filtered_segments) / self.sr
            cut_duration = total_duration - kept_duration
            kept_percentage = (kept_duration / total_duration) * 100 if total_duration > 0 else 0
            
            self.log_status(f"\n処理完了:")
            self.log_status(f"  総時間: {total_duration:.2f}秒")
            self.log_status(f"  残された時間: {kept_duration:.2f}秒 ({kept_percentage:.1f}%)")
            self.log_status(f"  カットされた時間: {cut_duration:.2f}秒 ({100-kept_percentage:.1f}%)")
            
            # Display processed waveform
            self.display_waveform(y, "処理後の音声 (青=残された部分, 灰色=カットされた部分)", filtered_segments)
            
            # Enable play and visualize buttons
            self.play_btn.config(state=tk.NORMAL)
            self.visualize_btn.config(state=tk.NORMAL)
            
        except Exception as e:
            messagebox.showerror("エラー", f"音声処理に失敗しました: {str(e)}")
            self.log_status(f"エラー: {str(e)}")
            import traceback
            self.log_status(traceback.format_exc())
            
    def play_processed(self):
        if self.y_processed is None:
            messagebox.showwarning("警告", "まず音声を処理してください")
            return
            
        try:
            self.log_status("\n処理後の音声を再生中...")
            self.play_btn.config(state=tk.DISABLED)
            
            def play_thread():
                sd.play(self.y_processed, self.sr)
                sd.wait()
                self.root.after(0, lambda: self.play_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.log_status("再生完了"))
            
            thread = threading.Thread(target=play_thread)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("エラー", f"音声の再生に失敗しました: {str(e)}")
            self.log_status(f"エラー: {str(e)}")
            self.play_btn.config(state=tk.NORMAL)
            
    def start_visualization(self):
        if self.y_processed is None or not self.filtered_segments:
            messagebox.showwarning("警告", "まず音声を処理してください")
            return
            
        try:
            self.log_status("\n可視化を開始します...")
            
            # Run nakigoe.py processing
            import subprocess
            
            response = messagebox.askyesno(
                "可視化開始",
                "可視化処理を開始します。\n処理には時間がかかる場合があります。\n続行しますか？"
            )
            
            if response:
                self.log_status("UMAP可視化処理を実行中...")
                self.log_status("nakigoe.pyを実行してください")
                messagebox.showinfo(
                    "可視化",
                    "満足のいく前処理が完了しました。\nnakigoe.pyを実行して可視化を開始してください。"
                )
            
        except Exception as e:
            messagebox.showerror("エラー", f"可視化の開始に失敗しました: {str(e)}")
            self.log_status(f"エラー: {str(e)}")

def main():
    root = tk.Tk()
    app = AudioPreprocessingGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
