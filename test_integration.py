#!/usr/bin/env python3
"""Integration test for preprocessing GUI with actual audio file"""

import os
import sys
import numpy as np
import librosa
import scipy.signal as signal
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

def test_with_audio_file(file_path):
    """Test preprocessing logic with an actual audio file"""
    
    print(f"Testing with audio file: {file_path}")
    
    # Load audio
    print("\n1. Loading audio file...")
    y_original, sr = librosa.load(file_path, sr=None)
    duration = len(y_original) / sr
    print(f"   ✓ Loaded: {duration:.2f} seconds, {sr} Hz")
    
    # Apply high-pass filter
    print("\n2. Applying high-pass filter...")
    cutoff = 3000
    b, a = signal.butter(4, cutoff / (sr / 2), btype="high")
    y = signal.filtfilt(b, a, y_original)
    print(f"   ✓ High-pass filter applied ({cutoff} Hz)")
    
    # Detect sound intervals
    print("\n3. Detecting sound intervals...")
    top_db = 45
    intervals = librosa.effects.split(y, top_db=top_db)
    print(f"   ✓ Detected {len(intervals)} intervals")
    
    # Filter by duration
    print("\n4. Filtering by duration...")
    min_duration = 0.1
    segments = []
    for start, end in intervals:
        duration_sec = (end - start) / sr
        if duration_sec >= min_duration:
            segments.append((start, end))
    print(f"   ✓ {len(segments)} segments after duration filter")
    
    # Filter non-bird sounds
    print("\n5. Filtering non-bird sounds...")
    filtered_segments = []
    for i, (start, end) in enumerate(segments):
        segment = y[start:end]
        
        # Calculate features
        zcr = librosa.feature.zero_crossing_rate(segment)[0]
        zcr_mean = np.mean(zcr)
        
        spectral_centroids = librosa.feature.spectral_centroid(y=segment, sr=sr)[0]
        spectral_centroid_mean = np.mean(spectral_centroids)
        
        spectral_rolloff = librosa.feature.spectral_rolloff(y=segment, sr=sr, roll_percent=0.85)[0]
        spectral_rolloff_mean = np.mean(spectral_rolloff)
        
        rms = librosa.feature.rms(y=segment)[0]
        rms_mean = np.mean(rms)
        
        # Filter criteria
        is_bird_sound = True
        reasons = []
        
        if spectral_centroid_mean < 2500:
            is_bird_sound = False
            reasons.append("low spectral centroid")
        
        if zcr_mean < 0.1:
            is_bird_sound = False
            reasons.append("low ZCR")
        
        if rms_mean < 0.005:
            is_bird_sound = False
            reasons.append("low RMS")
        
        if spectral_rolloff_mean < 3500:
            is_bird_sound = False
            reasons.append("low spectral rolloff")
        
        if is_bird_sound:
            filtered_segments.append((start, end))
            print(f"   ✓ Segment {i+1}: KEPT (centroid={spectral_centroid_mean:.0f}Hz, zcr={zcr_mean:.3f}, rms={rms_mean:.4f})")
        else:
            print(f"   ✗ Segment {i+1}: REJECTED ({', '.join(reasons)})")
    
    print(f"\n   Total: {len(filtered_segments)} segments after non-bird filter")
    
    # Create processed audio
    print("\n6. Creating processed audio...")
    y_processed = np.zeros_like(y)
    for start, end in filtered_segments:
        y_processed[start:end] = y[start:end]
    print("   ✓ Processed audio created")
    
    # Calculate statistics
    print("\n7. Statistics:")
    total_duration = len(y) / sr
    kept_duration = sum((end - start) for start, end in filtered_segments) / sr
    cut_duration = total_duration - kept_duration
    kept_percentage = (kept_duration / total_duration) * 100 if total_duration > 0 else 0
    
    print(f"   Total duration: {total_duration:.2f} seconds")
    print(f"   Kept duration: {kept_duration:.2f} seconds ({kept_percentage:.1f}%)")
    print(f"   Cut duration: {cut_duration:.2f} seconds ({100-kept_percentage:.1f}%)")
    
    # Create visualization
    print("\n8. Creating visualization...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Original waveform
    times = np.arange(len(y_original)) / sr
    ax1.plot(times, y_original, linewidth=0.5, color='blue')
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('Amplitude')
    ax1.set_title('Original Audio')
    ax1.grid(True, alpha=0.3)
    
    # Processed waveform
    ax2.plot(times, y, linewidth=0.5, alpha=0.7, color='gray', label='Cut parts')
    first_segment = True
    for start, end in filtered_segments:
        segment_times = times[start:end]
        segment_y = y[start:end]
        label = 'Kept parts' if first_segment else ''
        ax2.plot(segment_times, segment_y, linewidth=0.5, color='blue', label=label)
        first_segment = False
    
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('Amplitude')
    ax2.set_title('Processed Audio (Blue = Kept, Gray = Cut)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    fig.tight_layout()
    output_path = '/tmp/bird_audio_samples/test_result.png'
    fig.savefig(output_path, dpi=100, bbox_inches='tight')
    print(f"   ✓ Visualization saved to: {output_path}")
    
    return True

def main():
    test_file = '/tmp/bird_audio_samples/test_bird_calls.wav'
    
    if not os.path.exists(test_file):
        print(f"Error: Test file not found: {test_file}")
        print("Please run the audio generation script first.")
        return False
    
    try:
        print("="*70)
        print("INTEGRATION TEST: Audio Preprocessing")
        print("="*70)
        
        success = test_with_audio_file(test_file)
        
        if success:
            print("\n" + "="*70)
            print("SUCCESS: All tests passed!")
            print("="*70)
            return True
        else:
            print("\n" + "="*70)
            print("FAILED: Some tests failed")
            print("="*70)
            return False
            
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
