# Bird Call UMAP - 試行錯誤プロジェクト 🐦
<img width="800" height="600" alt="UMAP 3kHz以上" src="https://github.com/user-attachments/assets/5c9b5964-8775-444e-88cf-07e2e3d56f79" />
このプロジェクトは、鳥の鳴き声を機械学習とUMAPを用いてクラスタリング・可視化する**実験的なプロトタイプ**です。

## 概要

WAVファイルから鳥の鳴き声を自動抽出し、MFCCなどの音響特徴量を用いてクラスタリングを行い、UMAPで2次元空間に可視化します。

## 主な機能（開発中）

- **音声ファイルの選択**: ファイルダイアログでWAVファイルを選択
- **前処理**:
  - ハイパスフィルタ（3000Hz以上）で高周波成分を抽出
  - 音声区間の自動検出（無音区間の除去）
- **特徴抽出**: MFCC（メル周波数ケプストラム係数）の計算
- **クラスタリング**: K-Meansによる教師なし学習
- **可視化**:
  - UMAPを用いた2次元マッピング
  - スペクトログラムの表示
  - クラスタごとの代表的な鳴き声の可視化
- **音声ファイルの出力**: クラスタごとに代表的な鳴き声セグメントをWAV形式で保存

## 環境構築

### 必要なライブラリ

```bash
pip install librosa matplotlib numpy scikit-learn umap-learn soundfile scipy
```

### 推奨環境

- Python 3.8以上
- tkinter（Pythonに付属）

## 使用方法

```bash
python nakigoe.py
```

実行するとファイル選択ダイアログが開きます。分析対象のWAVファイルを選択してください。

## 出力

- **cluster_segments/** ディレクトリ: クラスタごとの代表的な鳴き声セグメント（WAV形式）
- **UMAP可視化**: クラスタ分布の2次元プロット
- **スペクトログラム**: 各クラスタの代表的な鳴き声の時間周波数解析
- **コンソール出力**: 各クラスタに含まれるフレームの時間情報

## 現在の試行錯誤・課題 ⚠️

このプロジェクトはまだ開発初期段階です。以下のような改善が検討されています：

### パラメータの調整が必要
- **ハイパスフィルタの周波数**: 現在は3000Hzで固定。鳥の種類によって最適値が異なる可能性
- **音声区間検出（top_db値）**: 現在45で固定。環境ノイズレベルに応じた動的調整が必要
- **フレーム長・ホップ長**: 0.2秒で固定。より短い周期での分析が必要な場合も検討中
- **K-Meansのクラスタ数（k=4）**: 自動決定メカニズムの実装予定
- **MFCC係数数（n_mfcc=20）**: 最適値の検証が必要

### 既知の問題
- パラメータを手動で変更する必要がある（設定ファイル化を検討中）
- 単一ファイルの分析のみに対応（複数ファイルの一括処理未実装）
- 出力ファイルの重複上書きの問題あり
- クラスタの有意性評価がない

## 注意事項

- このコードは**実験段階**です。本番環境での使用は推奨されません
- パラメータ調整には試行錯誤が必要な場合があります
- 鳥の種類や録音環境によって結果が大きく変わる可能性があります

## 参考資料

- [librosa - Music and Audio Analysis](https://librosa.org/)
- [UMAP - Uniform Manifold Approximation and Projection](https://umap-learn.readthedocs.io/)
- [scikit-learn - K-Means Clustering](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html)

## ライセンス

このプロジェクトは MIT ライセンスで公開されています。詳細は [LICENSE](LICENSE) をご覧ください。  
This project is released under the MIT License. See [LICENSE](LICENSE) for details.


## 貢献

このプロジェクトはまだ試行錯誤の段階のため、フィードバックやご提案をお待ちしています。
