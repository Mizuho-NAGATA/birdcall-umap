# GUI Enhancement Implementation Summary

## Overview
This document describes the enhancements made to the nakigoe.py birdcall analysis tool.

## Changes Implemented

### 1. Save Button Functionality Enhancement ✓

**Before:**
- Button text: "💾 保存"
- Functionality: Save current single frame via file dialog
- User had to specify filename for each save

**After:**
- Button text: "💾 一括保存"
- Functionality: Batch save all non-excluded frames
- User selects a directory (not individual files)
- Files automatically named: `frame_{index}_{cluster}.wav`

**Implementation Details:**
- Method renamed: `save_current_frame()` → `save_all_frames()`
- Uses `filedialog.askdirectory()` instead of `asksaveasfilename()`
- Iterates through all frames where `keep_flags[i] == True`
- Displays success message with count of saved files

**Location in code:** Lines 445-480

### 2. Parameter Adjustment GUI ✓

A new parameter adjustment section has been added to the FrameFilteringGUI.

**New GUI Components:**

1. **Frame Length Slider** (フレーム長)
   - Range: 0.1 - 0.5 seconds
   - Resolution: 0.05 seconds
   - Default: 0.2 seconds
   - Updates label in real-time

2. **Hop Length Slider** (ホップ長)
   - Range: 0.1 - 0.5 seconds
   - Resolution: 0.05 seconds
   - Default: 0.2 seconds
   - Updates label in real-time

3. **Highpass Filter Cutoff Slider** (ハイパスフィルタ)
   - Range: 1000 - 6000 Hz
   - Resolution: 100 Hz
   - Default: 3000 Hz
   - Updates label in real-time

4. **Energy Threshold Slider** (エネルギー閾値)
   - Range: 20 - 60
   - Resolution: 1
   - Default: 45
   - Updates label in real-time

5. **Apply Parameters Button** (パラメーター適用)
   - Triggers reprocessing with new parameters
   - Shows confirmation dialog before proceeding
   - Closes GUI and restarts processing loop

**Implementation Details:**
- All sliders use Tkinter's `Scale` widget
- Each slider has a corresponding update method
- Current values displayed with labels
- Parameter values stored in class attributes
- GUI window size increased: 700x500 → 700x750

**Location in code:** Lines 194-289

### 3. Reprocessing Loop ✓

**New Architecture:**
- Main processing wrapped in `while reprocess:` loop
- Parameters stored in `processing_params` dictionary
- GUI returns dictionary with:
  - `keep_flags`: List of excluded/kept frames
  - `reprocess_requested`: Boolean flag
  - `params`: Updated parameter values
- When reprocessing requested:
  - Updates `processing_params`
  - Sets `reprocess = True`
  - Continues loop from beginning

**Location in code:** Lines 651-672

## GUI Layout

```
┌─────────────────────────────────────────────────────────────┐
│ フレームフィルタリング - 鳥の鳴き声選別                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  フレーム 1 / 100                                            │
│  時間: 0.50 秒                                               │
│  クラスタ: 2                                                 │
│  状態: 保持                                                  │
│                                                               │
│  除外済み: 5 / 100                                           │
│                                                               │
│    [◀ 前へ]         [次へ ▶]                                │
│                                                               │
│    [▶ 再生]        [✗ 除外]        [💾 一括保存]            │
│                                                               │
│    [▶▶ 全再生]     [✓ 完了]        [■ 停止]                 │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│ 使い方:                                                      │
│ ・「前へ」「次へ」: フレームを移動して自動再生              │
│ ・「再生」: 現在のフレームを再生                            │
│ ・「除外」: 現在のフレームを除外リストに追加                │
│ ・「一括保存」: 除外していないすべてのフレームをディレクトリ│
│                 に保存                                       │
│ ・「全再生」: すべてのフレームを順番に再生                  │
│ ・「完了」: フィルタリングを終了してUMAP可視化へ            │
├─────────────────────────────────────────────────────────────┤
│ ┌─ パラメーター調整 ────────────────────────────────────┐ │
│ │                                                         │ │
│ │ フレーム長:   0.20 秒  [========|====================] │ │
│ │                                                         │ │
│ │ ホップ長:     0.20 秒  [========|====================] │ │
│ │                                                         │ │
│ │ ハイパスフィルタ: 3000 Hz  [=======|================] │ │
│ │                                                         │ │
│ │ エネルギー閾値:   45      [=======|================]   │ │
│ │                                                         │ │
│ │            [パラメーター適用（再処理）]                │ │
│ │                                                         │ │
│ │ 注: パラメーターを変更後、「パラメーター適用」ボタンを  │ │
│ │     クリックすると新しいパラメーターで音声処理を        │ │
│ │     再実行します（GUIは一旦閉じます）                   │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## File Structure Changes

**Before:**
```
nakigoe.py (560 lines)
├── Imports
├── File selection
├── Audio processing (fixed parameters)
├── GUI class definition
└── Visualization
```

**After:**
```
nakigoe.py (775 lines)
├── Imports
├── FrameFilteringGUI class (complete)
├── File selection
├── Parameter initialization
└── Main processing loop (reprocessable)
    ├── Audio loading
    ├── Filtering (with parameters)
    ├── Frame extraction (with parameters)
    ├── Clustering
    ├── GUI interaction
    └── Visualization
```

## Testing

Run the structure validation test:
```bash
python3 test_gui_structure.py
```

This validates:
- ✓ Single FrameFilteringGUI class definition
- ✓ All required methods present
- ✓ Parameter attributes defined
- ✓ GUI sliders implemented
- ✓ Reprocessing loop structure
- ✓ Batch save functionality

## Usage Example

1. **Start the application:**
   ```bash
   python3 nakigoe.py
   ```

2. **Select WAV file** via file dialog

3. **View processing results** in GUI

4. **Adjust parameters** using sliders:
   - Move sliders to desired values
   - Click "パラメーター適用（再処理）"
   - Confirm to restart with new parameters

5. **Filter frames:**
   - Use "再生" to listen to current frame
   - Use "除外" to exclude unwanted frames
   - Navigate with "前へ"/"次へ"

6. **Save all kept frames:**
   - Click "一括保存"
   - Select output directory
   - All non-excluded frames saved automatically

7. **Complete filtering:**
   - Click "完了"
   - View UMAP visualization

## Technical Notes

- Window size increased to accommodate parameter controls (700x750)
- All parameter changes require reprocessing for accuracy
- Original audio data is reloaded on each reprocessing cycle
- Filter states are reset on reprocessing
- Naming convention for saved files: `frame_{index}_{cluster}.wav`
- Directory selection prevents file overwrite issues

## Dependencies

No new dependencies added. All functionality uses existing libraries:
- tkinter (GUI)
- librosa (audio processing)
- sounddevice (audio playback)
- soundfile (WAV file I/O)
- sklearn (clustering)
- umap (visualization)
