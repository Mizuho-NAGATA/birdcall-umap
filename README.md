![Clipboard_02-15-2026_01](https://github.com/user-attachments/assets/7b696a2f-73ea-4d6a-bb61-e06f75949502)
## Bird Call Clustering with UMAP

鳥の鳴き声のWAVファイルを読み込み、音響特徴量（MFCC）を抽出してクラスタリングし、2次元に可視化するシンプルなツールです。
音声を短時間フレームに分割し、似た鳴き声パターンを自動でグループ化します。動物種を問わず、鳴き声を可視化したいときにどうぞ。    

これは実験的な作品です。自動クラスタリングの結果は必ずしも生物学的・行動学的に正しいとは限りません。  
結果の解釈や、分類数の妥当性は、人間が代表音声を聞いて判断する必要があります。  
サンプル画像は、セキセイインコ オス 2歳 360秒 録音の結果です。

This is a simple tool that reads WAV files of bird calls, extracts acoustic features (MFCC), clusters them, and visualizes the results in two dimensions. It divides the audio into short frames and automatically groups similar call patterns. Feel free to use it when you want to visualize your own bird's chirping.  

This is an experimental work. The results of automatic clustering are not necessarily biologically or behaviorally accurate.  
Interpretation of results and the validity of classification numbers require human judgment based on listening to representative audio samples.  
The sample image shows results from recording a 2-year-old male budgerigar for 360 seconds. 

---

## 概要

このプロジェクトは以下の処理を自動で行います：

1. WAVファイルをGUIで選択
2. 0.2秒ごとに音声を分割
3. MFCC特徴量を抽出
4. K-meansでクラスタリング
5. UMAPで2次元に次元削減
6. 散布図として可視化

鳥の鳴き声の種類分析や、音声パターン探索の初期解析に適しています。

---

## 画面の見方
- 点：短時間フレーム（時間窓）1 点 = 約 0.2 秒（デフォルト）
- 色：同じクラスタに属する点（似た音）
- 横・縦軸：UMAP による次元削減後の座標（数値そのものは「意味のある尺度」ではなく視覚的な類似度表示です）
- 使い方のヒント：プロット上で近い点は音響的に似ています。代表的なクラスタの音を聞いて、人間が意味づけ（このクラスタは「さえずり」か「呼び声」か等）をすると良いです。

---

## 特徴

* WAVファイルをダイアログから簡単に選択
* 無音区間を自動で除外
* MFCCの平均＋分散を特徴量として使用
* クラスタ数を変更可能
* UMAPによる視覚的に分かりやすい分布表示

---

## 必要環境

* Python 3.10+
* 以下のPythonライブラリ：

```
librosa
matplotlib
numpy
scikit-learn
umap-learn
tkinter
```

インストール例：

```bash
pip install librosa matplotlib numpy scikit-learn umap-learn
```

（tkinterは多くの環境で標準搭載されています）

---

## 使い方
### 事前準備
**録音**：  
スマートフォンで OK。あなたのペットの声を録音します。あるいはビデオ録画して音声を wav ファイルとして抽出してもいいです。

**音声ファイルの転送**：  
録音した音声ファイルをパソコンに転送します。必要に応じて wav ファイルに変換します。

### パソコンの準備
**Python ファイルのダウンロード**：  
画面上の緑色のcodeボタンをクリックし、Download ZIP をクリックしてお好みの場所にファイルをダウンロード。  

**Python スクリプトの実行**：  
上記のPython と Python ライブラリをインストールする。次に、コマンドプロンプトを開いて、下記をコピペして Enter キーを押す。

```bash
python main.py
```

1. ファイル選択ダイアログが開きます
2. WAVファイルを選択します
3. クラスタリング結果が散布図で表示されます

---

## パラメータ調整

コード内の以下の値を変更できます：

```python
k = 4  # クラスタ数
frame_length = int(sr * 0.2)  # フレーム長
```

* クラスタ数を増やすと、より細かく分類されます
* フレーム長を短くすると時間分解能が上がります

---

## 出力例

* 各点：音声フレーム
* 色：クラスタ
* 距離：音響的な類似度

似た鳴き声は近くに配置されます。

---

## 想定用途

* 鳥の鳴き声のパターン分析の第一歩
* とにかく動物の鳴き声を可視化したいとき

---

## ライセンス

MIT License

