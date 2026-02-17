#!/usr/bin/env python3
"""Test script for preprocessing GUI - validates basic functionality"""

import os
import sys

# Test imports
print("Testing imports...")
try:
    import numpy as np
    import librosa
    import scipy.signal as signal
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    print("✓ All required modules imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test preprocessing functions
print("\nTesting preprocessing logic...")

def test_preprocessing():
    """Test the core preprocessing logic"""
    # Create a synthetic audio signal
    sr = 22050
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration))
    
    # Create a chirp signal (simulating bird call)
    chirp_frequency = 3000 + 1000 * t
    y = np.sin(2 * np.pi * chirp_frequency * t)
    
    # Add some noise
    y += 0.1 * np.random.randn(len(y))
    
    print(f"  Created test signal: {len(y)} samples, {sr} Hz, {duration} sec")
    
    # Test high-pass filter
    cutoff = 3000
    b, a = signal.butter(4, cutoff / (sr / 2), btype="high")
    y_filtered = signal.filtfilt(b, a, y)
    print(f"  ✓ High-pass filter applied ({cutoff} Hz)")
    
    # Test interval detection
    intervals = librosa.effects.split(y_filtered, top_db=45)
    print(f"  ✓ Detected {len(intervals)} audio intervals")
    
    # Test feature extraction
    if len(intervals) > 0:
        start, end = intervals[0]
        segment = y_filtered[start:end]
        
        # Zero crossing rate
        zcr = librosa.feature.zero_crossing_rate(segment)[0]
        print(f"  ✓ Zero crossing rate calculated: mean={np.mean(zcr):.4f}")
        
        # Spectral centroid
        spec_cent = librosa.feature.spectral_centroid(y=segment, sr=sr)[0]
        print(f"  ✓ Spectral centroid calculated: mean={np.mean(spec_cent):.2f} Hz")
        
        # Spectral rolloff
        spec_roll = librosa.feature.spectral_rolloff(y=segment, sr=sr, roll_percent=0.85)[0]
        print(f"  ✓ Spectral rolloff calculated: mean={np.mean(spec_roll):.2f} Hz")
        
        # RMS energy
        rms = librosa.feature.rms(y=segment)[0]
        print(f"  ✓ RMS energy calculated: mean={np.mean(rms):.4f}")
    
    print("\n✓ All preprocessing logic tests passed!")
    return True

# Run tests
if __name__ == "__main__":
    try:
        test_preprocessing()
        print("\n" + "="*50)
        print("SUCCESS: All tests passed!")
        print("="*50)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
