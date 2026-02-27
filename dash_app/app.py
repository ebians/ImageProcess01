"""
グレースケール画像処理ツール – Plotly Dash 版
==============================================
機能:
  1. 画像アップロード + 矩形切り取り
  2. メディアンフィルタ (3×3 / 5×5 / 7×7)
  3. レベル自動調整 + ヒストグラム表示
  4. 二値化 (閾値 t1 / t2) + 白画素カウント
  5. 結果テーブル + CSV エクスポート
"""

import base64
import csv
import io

import numpy as np
from PIL import Image
from scipy.ndimage import median_filter

import dash
from dash import dcc, html, dash_table, no_update, ctx
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go


# ============================================================
#  Image Processing Functions
# ============================================================

def decode_upload_to_gray(contents: str) -> np.ndarray:
    """dcc.Upload の contents → グレースケール ndarray."""
    _, b64 = contents.split(",", 1)
    img = Image.open(io.BytesIO(base64.b64decode(b64)))
    return np.array(img.convert("L"))


def arr_to_b64(arr: np.ndarray) -> str:
    """ndarray → base64 PNG (Store 保存用)."""
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def b64_to_arr(b64str: str) -> np.ndarray:
    """base64 PNG → ndarray."""
    return np.array(
        Image.open(io.BytesIO(base64.b64decode(b64str))).convert("L")
    )


def arr_to_data_uri(arr: np.ndarray) -> str:
    """ndarray → data:image/png;base64,… (html.Img src 用)."""
    return f"data:image/png;base64,{arr_to_b64(arr)}"


def apply_median(arr: np.ndarray, kernel_size: int) -> np.ndarray:
    return median_filter(arr, size=kernel_size).astype(np.uint8)


def compute_histogram(arr: np.ndarray) -> list:
    return np.bincount(arr.flatten(), minlength=256).tolist()


def analyse_histogram(hist: list) -> dict:
    total = sum(hist)
    if total == 0:
        return {"skewed": False, "min_val": 0, "max_val": 255}
    cum, min_val = 0, 0
    for i in range(256):
        cum += hist[i]
        if cum / total >= 0.01:
            min_val = i
            break
    cum, max_val = 0, 255
    for i in range(255, -1, -1):
        cum += hist[i]
        if cum / total >= 0.01:
            max_val = i
            break
    return {"skewed": (max_val - min_val) < 200,
            "min_val": min_val, "max_val": max_val}


def apply_level_adjustment(arr: np.ndarray, mn: int, mx: int) -> np.ndarray:
    r = mx - mn
    if r <= 0:
        return arr.copy()
    return np.clip((arr.astype(np.float64) - mn) / r * 255, 0, 255).astype(
        np.uint8
    )


def apply_threshold(arr: np.ndarray, t: int) -> np.ndarray:
    return np.where(arr <= t, np.uint8(0), np.uint8(255))


def count_white(arr: np.ndarray) -> int:
    return int(np.sum(arr == 255))


# ============================================================
#  Plotly Figure Builders
# ============================================================

def build_original_figure(arr: np.ndarray) -> go.Figure:
    """元画像を Heatmap で表示 (drawrect 対応)."""
    h, w = arr.shape
    fig = go.Figure(
        data=go.Heatmap(
            z=arr, colorscale="gray", zmin=0, zmax=255,
            showscale=False, zsmooth=False,
            hovertemplate="x=%{x}, y=%{y}<br>輝度=%{z}<extra></extra>",
        )
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed", scaleanchor="x",
                   constrain="domain", showticklabels=False,
                   showgrid=False, zeroline=False),
        xaxis=dict(constrain="domain", showticklabels=False,
                   showgrid=False, zeroline=False),
        margin=dict(l=0, r=0, t=0, b=0),
        dragmode="drawrect",
        newshape=dict(
            line=dict(color="#e74c3c", width=2),
            fillcolor="rgba(231,76,60,0.15)",
        ),
        plot_bgcolor="#f8f8f8",
        height=max(300, min(550, h + 20)),
    )
    return fig


def build_histogram_figure(hist: list, t1=None, t2=None) -> go.Figure:
    max_h = max(hist) if hist and max(hist) > 0 else 1
    fig = go.Figure(
        data=go.Bar(x=list(range(256)), y=hist,
                    marker_color="black", marker_line_width=0, width=1)
    )
    shapes, annotations = [], []
    if t1 is not None:
        shapes.append(dict(
            type="line", x0=t1, x1=t1, y0=0, y1=max_h * 1.05,
            line=dict(color="#e74c3c", width=2, dash="dash"),
        ))
        annotations.append(dict(
            x=t1, y=max_h * 1.08, text=f"t1={t1}",
            showarrow=False, font=dict(color="#e74c3c", size=11),
        ))
    if t2 is not None:
        shapes.append(dict(
            type="line", x0=t2, x1=t2, y0=0, y1=max_h * 1.05,
            line=dict(color="#2980b9", width=2, dash="dash"),
        ))
        annotations.append(dict(
            x=t2, y=max_h * 1.12, text=f"t2={t2}",
            showarrow=False, font=dict(color="#2980b9", size=11),
        ))
    fig.update_layout(
        shapes=shapes, annotations=annotations,
        xaxis=dict(title="輝度値", range=[-0.5, 255.5]),
        yaxis=dict(title="画素数"),
        bargap=0,
        margin=dict(l=60, r=20, t=20, b=50),
        plot_bgcolor="#f8f8f8",
        height=260,
    )
    return fig


# ============================================================
#  Dash App
# ============================================================

app = dash.Dash(
    __name__,
    title="グレースケール画像処理ツール",
    suppress_callback_exceptions=True,
)

# --- Stores ---
stores = html.Div([
    dcc.Store(id="store-original"),
    dcc.Store(id="store-adjusted"),
    dcc.Store(id="store-histogram"),
    dcc.Store(id="store-histogram-raw"),
    dcc.Store(id="store-filename"),
    dcc.Store(id="store-crop-coords"),
    dcc.Store(id="store-table", data=[]),
])

# ---- Section 1: Upload & Crop ----
section_upload = html.Section(className="step", children=[
    html.H2([html.Span("1", className="step-badge"),
             " 画像の読み込みと切り取り範囲の選択"]),
    dcc.Upload(
        id="upload-image",
        children=html.Div([
            html.Div([
                html.P("ここに画像をドラッグ＆ドロップ", className="drop-main"),
                html.P("または", style={"margin": "4px 0", "color": "#999",
                                         "fontSize": "0.85em"}),
                html.Button("画像ファイルを選択", className="btn"),
            ], className="drop-inner"),
            html.P("グレースケール画像（JPEG / PNG など）を選択してください",
                   className="hint"),
        ]),
        accept="image/*",
        className="upload-area",
        style_active={
            "borderColor": "#3498db",
            "backgroundColor": "#eaf2fb",
        },
    ),
    html.Div(id="crop-area", style={"display": "none"}, children=[
        html.P([
            "画像上でドラッグして切り取り範囲を選択し、ボタンを押してください",
            html.Br(),
            html.Small("（ツールバーの □ アイコンで四角形を描画できます）",
                       style={"color": "#999"}),
        ], className="hint"),
        dcc.Graph(
            id="original-graph",
            config={
                "modeBarButtonsToAdd": ["drawrect", "eraseshape"],
                "displayModeBar": True,
                "scrollZoom": True,
            },
        ),
        html.Div(className="controls", children=[
            html.Button(
                "切り取りとメディアンフィルタを適用",
                id="apply-btn", className="btn btn-primary", disabled=True,
            ),
            html.Label([
                "カーネルサイズ: ",
                dcc.Dropdown(
                    id="kernel-size",
                    options=[
                        {"label": "3×3", "value": 3},
                        {"label": "5×5", "value": 5},
                        {"label": "7×7", "value": 7},
                    ],
                    value=3, clearable=False,
                    style={"width": "100px", "display": "inline-block",
                           "verticalAlign": "middle"},
                ),
            ], className="kernel-label"),
        ]),
    ]),
])

# ---- Section 2: Median Filter Result ----
section_filter = html.Section(
    id="section-filter", className="step",
    style={"display": "none"}, children=[
        html.H2([html.Span("2", className="step-badge"),
                 " メディアンフィルタ適用後"]),
        html.Div(id="filter-status", className="status-bar"),
        html.Div(className="image-row", children=[
            html.Div(className="image-card", children=[
                html.H3("切り取り後（フィルタ適用前）"),
                html.Img(id="cropped-img", style={"maxWidth": "100%"}),
            ]),
            html.Div(className="image-card", children=[
                html.H3("メディアンフィルタ適用後"),
                html.Img(id="filtered-img", style={"maxWidth": "100%"}),
            ]),
        ]),
    ],
)

# ---- Section 3: Level Adjustment & Histogram ----
section_level = html.Section(
    id="section-level", className="step",
    style={"display": "none"}, children=[
        html.H2([html.Span("3", className="step-badge"),
                 " レベル調整とヒストグラム"]),
        html.Div(id="adjustment-info", className="info-box"),
        html.Div(className="image-row", children=[
            html.Div(className="image-card", children=[
                html.H3("レベル調整前ヒストグラム"),
                dcc.Graph(id="histogram-raw-graph",
                         config={"displayModeBar": False}),
            ]),
            html.Div(className="image-card", children=[
                html.H3("レベル調整後ヒストグラム"),
                dcc.Graph(id="histogram-graph",
                         config={"displayModeBar": False}),
            ]),
        ]),
        html.Div(className="image-row", style={"marginTop": "16px"}, children=[
            html.Div(className="image-card", children=[
                html.H3("フィルタ適用後（レベル調整前）"),
                html.Img(id="filtered-level-img", style={"maxWidth": "100%"}),
            ]),
            html.Div(className="image-card", children=[
                html.H3("レベル調整後の画像"),
                html.Img(id="adjusted-img", style={"maxWidth": "100%"}),
            ]),
        ]),
    ],
)

# ---- Section 4: Thresholding ----
section_threshold = html.Section(
    id="section-threshold", className="step",
    style={"display": "none"}, children=[
        html.H2([html.Span("4–6", className="step-badge"),
                 " 閾値設定と二値化"]),
        html.P([
            "ヒストグラムを参考に閾値を設定してください。", html.Br(),
            "0 〜 閾値の範囲が", html.Strong("黒画素"),
            "、それ以外が", html.Strong("白画素"), "になります。",
        ], className="hint"),
        html.Div(className="threshold-controls", children=[
            html.Div(className="threshold-group", children=[
                html.Label(["閾値1 (t1): ",
                            html.Strong(id="t1-display", children="128")]),
                dcc.Slider(id="t1-slider", min=0, max=255, step=1, value=128,
                          marks=None, updatemode="drag",
                          tooltip={"placement": "bottom",
                                   "always_visible": True}),
            ]),
            html.Div(className="threshold-group", children=[
                html.Label(["閾値2 (t2): ",
                            html.Strong(id="t2-display", children="200")]),
                dcc.Slider(id="t2-slider", min=0, max=255, step=1, value=200,
                          marks=None, updatemode="drag",
                          tooltip={"placement": "bottom",
                                   "always_visible": True}),
            ]),
        ]),
        html.Div(className="histogram-block", children=[
            html.H3("ヒストグラム（閾値マーカー付き）"),
            dcc.Graph(id="threshold-histogram-graph",
                     config={"displayModeBar": False}),
        ]),
        html.Div(className="image-row", children=[
            html.Div(className="image-card", children=[
                html.H3(id="binary1-title", children="二値化1 (t1 = 128)"),
                html.Img(id="binary1-img", style={"maxWidth": "100%"}),
                html.P(["白画素数: ",
                        html.Strong(id="white-count-1", children="—")],
                       className="pixel-count"),
            ]),
            html.Div(className="image-card", children=[
                html.H3(id="binary2-title", children="二値化2 (t2 = 200)"),
                html.Img(id="binary2-img", style={"maxWidth": "100%"}),
                html.P(["白画素数: ",
                        html.Strong(id="white-count-2", children="—")],
                       className="pixel-count"),
            ]),
        ]),
        html.Div(className="image-row", style={"marginTop": "16px"}, children=[
            html.Div(className="image-card", children=[
                html.H3("差分画像（二値化1 − 二値化2）"),
                html.Img(id="diff-img", style={"maxWidth": "100%"}),
                html.P(["差分画素数（t1で白 かつ t2で黒）: ",
                        html.Strong(id="diff-count", children="—")],
                       className="pixel-count"),
            ]),
        ]),
        html.Button("テーブルに追加", id="add-table-btn",
                    className="btn btn-success"),
    ],
)

# ---- Section 5: Results Table & CSV ----
section_table = html.Section(className="step", children=[
    html.H2([html.Span("7–8", className="step-badge"),
             " 結果テーブルと CSV 出力"]),
    dash_table.DataTable(
        id="results-table",
        columns=[
            {"name": "ファイル名",    "id": "filename"},
            {"name": "白画素数（t1）", "id": "count1"},
            {"name": "白画素数（t2）", "id": "count2"},
            {"name": "差分（t1−t2）", "id": "diff"},
            {"name": "差分/t1 (%)",  "id": "ratio"},
        ],
        data=[],
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#3498db", "color": "white",
            "fontWeight": "bold", "textAlign": "left",
        },
        style_cell={"padding": "10px 14px", "textAlign": "left",
                    "fontSize": "0.9em"},
        style_data_conditional=[
            {"if": {"state": "active"}, "backgroundColor": "#f0f7fd"},
        ],
    ),
    html.Button("CSV エクスポート", id="export-btn", className="btn",
                disabled=True),
    dcc.Download(id="download-csv"),
])

# ---- Full Layout ----
app.layout = html.Div(className="container", children=[
    html.H1("グレースケール画像処理ツール"),
    stores,
    section_upload,
    dcc.Loading(
        children=[section_filter, section_level, section_threshold],
        type="circle", color="#3498db",
    ),
    section_table,
])


# ============================================================
#  Callbacks
# ============================================================

# 1. Image upload -----------------------------------------------
@app.callback(
    [Output("store-original", "data"),
     Output("store-filename", "data"),
     Output("original-graph", "figure"),
     Output("crop-area", "style"),
     Output("apply-btn", "disabled", allow_duplicate=True),
     Output("store-crop-coords", "data", allow_duplicate=True),
     Output("section-filter", "style", allow_duplicate=True),
     Output("section-level", "style", allow_duplicate=True),
     Output("section-threshold", "style", allow_duplicate=True)],
    Input("upload-image", "contents"),
    State("upload-image", "filename"),
    prevent_initial_call=True,
)
def on_upload(contents, filename):
    if contents is None:
        return [no_update] * 9
    arr = decode_upload_to_gray(contents)
    fig = build_original_figure(arr)
    hide = {"display": "none"}
    return (
        arr_to_b64(arr),
        filename or "unknown",
        fig,
        {"display": "block"},
        True,          # apply disabled
        None,          # clear crop coords
        hide, hide, hide,
    )


# 2. Capture crop rectangle from drawn shapes -------------------
@app.callback(
    [Output("store-crop-coords", "data"),
     Output("apply-btn", "disabled")],
    Input("original-graph", "relayoutData"),
    prevent_initial_call=True,
)
def on_relayout(relayout_data):
    if not relayout_data:
        return no_update, no_update

    # Full shapes list (new shape drawn or shape erased)
    if "shapes" in relayout_data:
        shapes = relayout_data["shapes"]
        if shapes:
            s = shapes[-1]
            return (
                {"x0": s["x0"], "y0": s["y0"],
                 "x1": s["x1"], "y1": s["y1"]},
                False,
            )
        return None, True  # all shapes erased

    # Individual shape property updates (reshape / drag)
    shape_keys = [k for k in relayout_data if k.startswith("shapes[")]
    if shape_keys:
        indices = set()
        for k in shape_keys:
            idx = k.split("]")[0].split("[")[1]
            indices.add(int(idx))
        last_idx = max(indices)
        prefix = f"shapes[{last_idx}]"
        vals = {p: relayout_data.get(f"{prefix}.{p}")
                for p in ("x0", "y0", "x1", "y1")}
        if all(v is not None for v in vals.values()):
            return vals, False

    return no_update, no_update


# 3. Apply crop + filter + level adjustment ---------------------
@app.callback(
    [Output("store-adjusted", "data"),
     Output("store-histogram", "data"),
     Output("store-histogram-raw", "data"),
     Output("cropped-img", "src"),
     Output("filtered-img", "src"),
     Output("adjusted-img", "src"),
     Output("filtered-level-img", "src"),
     Output("filter-status", "children"),
     Output("adjustment-info", "children"),
     Output("adjustment-info", "className"),
     Output("histogram-raw-graph", "figure"),
     Output("histogram-graph", "figure"),
     Output("section-filter", "style"),
     Output("section-level", "style"),
     Output("section-threshold", "style"),
     Output("t1-slider", "value"),
     Output("t2-slider", "value")],
    Input("apply-btn", "n_clicks"),
    [State("store-original", "data"),
     State("store-crop-coords", "data"),
     State("kernel-size", "value")],
    prevent_initial_call=True,
)
def on_apply(n_clicks, original_b64, crop, kernel_size):
    if not original_b64 or not crop:
        return [no_update] * 17

    original = b64_to_arr(original_b64)
    h, w = original.shape

    x0 = max(0, int(round(min(crop["x0"], crop["x1"]))))
    x1 = min(w, int(round(max(crop["x0"], crop["x1"]))))
    y0 = max(0, int(round(min(crop["y0"], crop["y1"]))))
    y1 = min(h, int(round(max(crop["y0"], crop["y1"]))))

    if (x1 - x0) < 2 or (y1 - y0) < 2:
        return [no_update] * 17

    # Crop
    cropped = original[y0:y1, x0:x1]

    # Median filter
    filtered = apply_median(cropped, kernel_size)
    filter_msg = (
        f"メディアンフィルタ（{kernel_size}×{kernel_size}）適用済み"
        f" – {x1 - x0}×{y1 - y0} px"
    )

    # Level adjustment
    raw_hist = compute_histogram(filtered)
    analysis = analyse_histogram(raw_hist)

    if analysis["skewed"]:
        adjusted = apply_level_adjustment(
            filtered, analysis["min_val"], analysis["max_val"]
        )
        info_text = (
            f"ヒストグラムが偏っています"
            f"（有効範囲: {analysis['min_val']}–{analysis['max_val']} / 255）。"
            f"レベル調整を自動適用しました。"
        )
        info_class = "info-box warning visible"
    else:
        adjusted = filtered
        info_text = "ヒストグラムは十分に分散しています。レベル調整は不要です。"
        info_class = "info-box info visible"

    histogram = compute_histogram(adjusted)
    show = {"display": "block"}

    return (
        arr_to_b64(adjusted),
        histogram,
        raw_hist,
        arr_to_data_uri(cropped),
        arr_to_data_uri(filtered),
        arr_to_data_uri(adjusted),
        arr_to_data_uri(filtered),  # レベル調整前画像
        filter_msg,
        info_text,
        info_class,
        build_histogram_figure(raw_hist),
        build_histogram_figure(histogram),
        show, show, show,
        128, 200,  # reset sliders
    )


# 4a. Threshold histogram marker – clientside (instant) ----------
app.clientside_callback(
    """
    function(t1, t2, histogram) {
        if (!histogram || histogram.length === 0) {
            return window.dash_clientside.no_update;
        }
        var maxH = Math.max(...histogram);
        if (maxH === 0) maxH = 1;
        var shapes = [];
        var annotations = [];
        if (t1 != null) {
            shapes.push({type:'line', x0:t1, x1:t1, y0:0, y1:maxH*1.05,
                         line:{color:'#e74c3c', width:2, dash:'dash'}});
            annotations.push({x:t1, y:maxH*1.08, text:'t1='+t1,
                              showarrow:false, font:{color:'#e74c3c', size:11}});
        }
        if (t2 != null) {
            shapes.push({type:'line', x0:t2, x1:t2, y0:0, y1:maxH*1.05,
                         line:{color:'#2980b9', width:2, dash:'dash'}});
            annotations.push({x:t2, y:maxH*1.12, text:'t2='+t2,
                              showarrow:false, font:{color:'#2980b9', size:11}});
        }
        // Build bar trace
        var x = []; var y = [];
        for (var i = 0; i < 256; i++) { x.push(i); y.push(histogram[i]); }
        return {
            data: [{type:'bar', x:x, y:y,
                    marker:{color:'black', line:{width:0}}, width:1}],
            layout: {
                shapes: shapes, annotations: annotations,
                xaxis: {title:'輝度値', range:[-0.5,255.5]},
                yaxis: {title:'画素数'},
                bargap: 0,
                margin: {l:60, r:20, t:20, b:50},
                plot_bgcolor: '#f8f8f8',
                height: 260
            }
        };
    }
    """,
    Output("threshold-histogram-graph", "figure"),
    [Input("t1-slider", "value"),
     Input("t2-slider", "value")],
    State("store-histogram", "data"),
)

# 4b. Threshold images – server callback -------------------------
@app.callback(
    [Output("binary1-img", "src"),
     Output("binary2-img", "src"),
     Output("diff-img", "src"),
     Output("white-count-1", "children"),
     Output("white-count-2", "children"),
     Output("diff-count", "children"),
     Output("binary1-title", "children"),
     Output("binary2-title", "children"),
     Output("t1-display", "children"),
     Output("t2-display", "children")],
    [Input("t1-slider", "value"),
     Input("t2-slider", "value")],
    [State("store-adjusted", "data"),
     State("store-histogram", "data")],
    prevent_initial_call=True,
)
def on_threshold(t1, t2, adjusted_b64, histogram):
    if not adjusted_b64 or not histogram:
        return [no_update] * 10

    adjusted = b64_to_arr(adjusted_b64)

    bin1 = apply_threshold(adjusted, t1)
    bin2 = apply_threshold(adjusted, t2)

    # 差分画像: グレー背景に差分領域を青50%アルファで重畳
    h_img, w_img = adjusted.shape
    diff_rgba = np.zeros((h_img, w_img, 4), dtype=np.uint8)
    # 背景: グレースケール画像をそのまま
    diff_rgba[:, :, 0] = adjusted
    diff_rgba[:, :, 1] = adjusted
    diff_rgba[:, :, 2] = adjusted
    diff_rgba[:, :, 3] = 255

    mask_diff = (bin1 == 255) & (bin2 == 0)  # t1で白 かつ t2で黒
    # 青(41,128,185)を50%アルファでブレンド
    overlay_r, overlay_g, overlay_b, alpha = 41, 128, 185, 0.5
    blend_r = (adjusted * (1 - alpha) + overlay_r * alpha).astype(np.uint8)
    blend_g = (adjusted * (1 - alpha) + overlay_g * alpha).astype(np.uint8)
    blend_b = (adjusted * (1 - alpha) + overlay_b * alpha).astype(np.uint8)
    diff_rgba[mask_diff, 0] = blend_r[mask_diff]
    diff_rgba[mask_diff, 1] = blend_g[mask_diff]
    diff_rgba[mask_diff, 2] = blend_b[mask_diff]

    # 両方白
    mask_both_white = (bin1 == 255) & (bin2 == 255)
    diff_rgba[mask_both_white, 0] = 255
    diff_rgba[mask_both_white, 1] = 255
    diff_rgba[mask_both_white, 2] = 255
    # 両方黒
    mask_both_black = (bin1 == 0) & (bin2 == 0)
    diff_rgba[mask_both_black, 0] = 40
    diff_rgba[mask_both_black, 1] = 40
    diff_rgba[mask_both_black, 2] = 40

    diff_count = int(np.sum(mask_diff))

    # 差分画像をPNG化
    diff_buf = io.BytesIO()
    Image.fromarray(diff_rgba).save(diff_buf, format="PNG")
    diff_uri = f"data:image/png;base64,{base64.b64encode(diff_buf.getvalue()).decode()}"

    return (
        arr_to_data_uri(bin1),
        arr_to_data_uri(bin2),
        diff_uri,
        f"{count_white(bin1):,}",
        f"{count_white(bin2):,}",
        f"{diff_count:,}",
        f"二値化1 (t1 = {t1})",
        f"二値化2 (t2 = {t2})",
        str(t1),
        str(t2),
    )


# 5. Add to table -----------------------------------------------
@app.callback(
    [Output("results-table", "data"),
     Output("store-table", "data"),
     Output("export-btn", "disabled")],
    Input("add-table-btn", "n_clicks"),
    [State("store-filename", "data"),
     State("t1-slider", "value"),
     State("t2-slider", "value"),
     State("white-count-1", "children"),
     State("white-count-2", "children"),
     State("store-table", "data")],
    prevent_initial_call=True,
)
def on_add_table(n_clicks, filename, t1, t2, cnt1, cnt2, table_data):
    if not filename or cnt1 == "—":
        return no_update, no_update, no_update
    table_data = table_data or []
    c1 = int(str(cnt1).replace(",", ""))
    c2 = int(str(cnt2).replace(",", ""))
    diff_val = c1 - c2
    ratio_val = (diff_val / c1 * 100) if c1 > 0 else 0.0
    table_data.append({
        "filename": filename,
        "count1": f"{c1:,}",
        "count2": f"{c2:,}",
        "diff": f"{diff_val:,}",
        "ratio": f"{ratio_val:.2f}",
    })
    return table_data, table_data, False


# 6. CSV export -------------------------------------------------
@app.callback(
    Output("download-csv", "data"),
    Input("export-btn", "n_clicks"),
    State("store-table", "data"),
    prevent_initial_call=True,
)
def on_export(n_clicks, table_data):
    if not table_data:
        return no_update
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ファイル名", "白画素数(t1)", "白画素数(t2)",
                     "差分(t1-t2)", "差分/t1(%)"])
    for row in table_data:
        writer.writerow([row["filename"], row["count1"], row["count2"],
                        row.get("diff", ""), row.get("ratio", "")])
    return dict(
        content="\ufeff" + buf.getvalue(),
        filename="image_analysis_results.csv",
        type="text/csv",
    )


# ============================================================
#  Entry Point
# ============================================================

server = app.server  # WSGI application (for Waitress / Gunicorn / nginx)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
