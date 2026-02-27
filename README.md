# ImageProcess01 — グレースケール画像処理ツール

グレースケール画像に対して **切り取り → メディアンフィルタ → レベル調整 → 二値化** を行い、白画素数をカウント・CSV 出力する Web アプリケーションです。  
Plotly Dash (Python) で実装されており、ブラウザ上で操作できます。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Dash](https://img.shields.io/badge/Dash-2.14%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 機能一覧

| ステップ | 機能 | 説明 |
|:---:|------|------|
| 1 | 画像アップロード＆切り取り | ドラッグ＆ドロップまたはファイル選択。Plotly の drawrect で矩形範囲を指定 |
| 2 | メディアンフィルタ | 3×3 / 5×5 / 7×7 カーネルサイズを選択して適用 |
| 3 | レベル調整＆ヒストグラム | ヒストグラムの偏りを自動検出し、レベル補正を適用。調整前後のヒストグラムと画像を並べて表示 |
| 4–6 | 閾値設定＆二値化 | スライダーで閾値 t1 / t2 を設定。ヒストグラムマーカーとリアルタイム同期（clientside callback）。差分画像（青 50% アルファ重畳）も表示 |
| 7–8 | 結果テーブル＆CSV | 白画素数・差分・差分比率をテーブルに蓄積し、CSV エクスポート |

---

## ディレクトリ構成

```
ImageProcess01/
├── README.md
├── sample_grayscale.png      # テスト用サンプル画像 (640×480)
├── generate_sample.py        # サンプル画像生成スクリプト
└── dash_app/
    ├── app.py                # Dash メインアプリケーション
    ├── requirements.txt      # Python 依存パッケージ
    ├── run.bat               # Windows 起動スクリプト
    ├── nginx.conf            # nginx リバースプロキシ設定（本番用）
    └── assets/
        └── style.css         # カスタム CSS
```

---

## セットアップ

### 前提条件

- Python 3.10 以上

### インストール

```bash
cd dash_app
pip install -r requirements.txt
```

### 起動（開発モード）

```bash
cd dash_app
python app.py
```

ブラウザで **http://localhost:8050** を開いてください。

Windows の場合は `run.bat` をダブルクリックでも起動できます。

### 起動（本番モード — Waitress）

```bash
cd dash_app
python -c "from waitress import serve; from app import server; serve(server, host='0.0.0.0', port=8050)"
```

### nginx リバースプロキシ（オプション）

`dash_app/nginx.conf` を nginx の設定に取り込んでください。  
nginx → `http://127.0.0.1:8050` へのリバースプロキシ構成です。

```
# nginx.conf の http ブロック内に追加:
include /path/to/dash_app/nginx.conf;
```

---

## 使い方

1. **画像を読み込む** — ドラッグ＆ドロップまたはファイル選択でグレースケール画像をアップロード
2. **切り取り範囲を選択** — ツールバーの □ アイコンで四角形を描画し、「切り取りとメディアンフィルタを適用」をクリック
3. **ヒストグラムを確認** — レベル調整前後のヒストグラムと画像を比較
4. **閾値を設定** — スライダーで t1 / t2 を調整し、二値化画像と差分画像を確認
5. **テーブルに追加** — 「テーブルに追加」で結果を蓄積
6. **CSV エクスポート** — 「CSV エクスポート」で結果をダウンロード

---

## サンプル画像の生成

リポジトリに含まれる `sample_grayscale.png` はテスト用です。  
再生成する場合：

```bash
pip install numpy Pillow scipy
python generate_sample.py
```

640×480、ヒストグラムにピーク 3 つ（110, 174, 230 付近）、輝度 80 未満なしの画像が生成されます。

---

## 技術スタック

| カテゴリ | 技術 |
|------|------|
| UI フレームワーク | Plotly Dash |
| グラフ描画 | Plotly.js |
| 画像処理 | Pillow, scipy.ndimage, NumPy |
| WSGI サーバー | Waitress（本番用） |
| リバースプロキシ | nginx（オプション） |

---

## ライセンス

MIT