// ============================================================
//  グレースケール画像処理ツール – app.js
// ============================================================

// ---------- Application State ----------
const state = {
  filename: '',
  filteredImageData: null,
  adjustedImageData: null,
  histogram: null,
  currentT1: 128,
  currentT2: 200,
  currentCount1: null,
  currentCount2: null,
  tableData: [],
  // crop selection
  isDragging: false,
  cropStart: null,
  cropEnd: null,
  cropRect: null,        // finalised rect
};

// ============================================================
//  Image Processing Functions
// ============================================================

/**
 * Convert an ImageData to grayscale (in-place, RGB ← luminance).
 */
function toGrayscale(imageData) {
  const d = imageData.data;
  for (let i = 0; i < d.length; i += 4) {
    const g = Math.round(0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]);
    d[i] = g; d[i + 1] = g; d[i + 2] = g;
  }
  return imageData;
}

/**
 * Apply an N×N median filter to a grayscale ImageData.
 * Edge pixels are handled by clamping (nearest-border replication).
 */
function applyMedianFilter(imageData, kernelSize) {
  const { width, height, data } = imageData;
  const half = Math.floor(kernelSize / 2);
  const n = kernelSize * kernelSize;
  const output = new Uint8ClampedArray(data.length);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const neighbors = new Array(n);
      let k = 0;
      for (let ky = -half; ky <= half; ky++) {
        for (let kx = -half; kx <= half; kx++) {
          const nx = Math.max(0, Math.min(width - 1, x + kx));
          const ny = Math.max(0, Math.min(height - 1, y + ky));
          neighbors[k++] = data[(ny * width + nx) * 4]; // R channel (grayscale)
        }
      }
      neighbors.sort((a, b) => a - b);
      const med = neighbors[Math.floor(n / 2)];
      const idx = (y * width + x) * 4;
      output[idx] = med;
      output[idx + 1] = med;
      output[idx + 2] = med;
      output[idx + 3] = 255;
    }
  }
  return new ImageData(output, width, height);
}

/**
 * Compute a 256-bin histogram from a grayscale ImageData (uses R channel).
 */
function computeHistogram(imageData) {
  const hist = new Array(256).fill(0);
  const d = imageData.data;
  for (let i = 0; i < d.length; i += 4) {
    hist[d[i]]++;
  }
  return hist;
}

/**
 * Analyse histogram skewness by finding the 1st–99th percentile range.
 * Returns { skewed, minVal, maxVal, range }.
 * "Skewed" = effective pixel range < 200 out of 256 (≈ 78% utilisation).
 */
function analyseHistogram(histogram) {
  const total = histogram.reduce((a, b) => a + b, 0);
  let cum = 0;
  let minVal = 0;
  for (let i = 0; i < 256; i++) {
    cum += histogram[i];
    if (cum / total >= 0.01) { minVal = i; break; }
  }
  cum = 0;
  let maxVal = 255;
  for (let i = 255; i >= 0; i--) {
    cum += histogram[i];
    if (cum / total >= 0.01) { maxVal = i; break; }
  }
  const range = maxVal - minVal;
  return { skewed: range < 200, minVal, maxVal, range };
}

/**
 * Stretch the pixel value range [minVal, maxVal] to [0, 255].
 */
function applyLevelAdjustment(imageData, minVal, maxVal) {
  const { width, height, data } = imageData;
  const range = maxVal - minVal;
  const output = new Uint8ClampedArray(data.length);
  for (let i = 0; i < data.length; i += 4) {
    const v = range > 0 ? Math.round((data[i] - minVal) / range * 255) : data[i];
    const c = Math.max(0, Math.min(255, v));
    output[i] = c; output[i + 1] = c; output[i + 2] = c; output[i + 3] = 255;
  }
  return new ImageData(output, width, height);
}

/**
 * Binary threshold: pixels ≤ threshold → black (0), others → white (255).
 */
function applyThreshold(imageData, threshold) {
  const { width, height, data } = imageData;
  const output = new Uint8ClampedArray(data.length);
  for (let i = 0; i < data.length; i += 4) {
    const v = data[i] <= threshold ? 0 : 255;
    output[i] = v; output[i + 1] = v; output[i + 2] = v; output[i + 3] = 255;
  }
  return new ImageData(output, width, height);
}

/**
 * Count white pixels (value === 255) in a grayscale ImageData.
 */
function countWhitePixels(imageData) {
  const d = imageData.data;
  let count = 0;
  for (let i = 0; i < d.length; i += 4) {
    if (d[i] === 255) count++;
  }
  return count;
}

// ============================================================
//  Canvas Utilities
// ============================================================

/** Put ImageData onto a canvas, resizing the canvas to match. */
function drawImageData(canvas, imageData) {
  canvas.width = imageData.width;
  canvas.height = imageData.height;
  canvas.getContext('2d').putImageData(imageData, 0, 0);
}

/**
 * Draw a grayscale histogram bar chart with optional threshold markers.
 * Canvas is resized to 512 × 200 (internal pixels).
 */
function drawHistogram(canvas, histogram, t1, t2) {
  const W = 512, H = 200, AXIS = 20;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  ctx.fillStyle = '#f8f8f8';
  ctx.fillRect(0, 0, W, H);

  const max = Math.max(...histogram);
  if (max === 0) return;

  const barW = W / 256;
  const plotH = H - AXIS;

  for (let i = 0; i < 256; i++) {
    const bh = (histogram[i] / max) * plotH;
    ctx.fillStyle = `rgb(${i},${i},${i})`;
    ctx.fillRect(i * barW, plotH - bh, barW + 0.5, bh);
  }

  // x-axis ticks
  ctx.fillStyle = '#666';
  ctx.font = '10px sans-serif';
  ctx.fillText('0', 2, H - 4);
  ctx.fillText('128', W / 2 - 8, H - 4);
  ctx.fillText('255', W - 22, H - 4);

  // threshold lines
  function drawThresholdLine(val, color, label, yLabel) {
    const x = val * barW;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 3]);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, plotH);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = color;
    ctx.font = 'bold 11px sans-serif';
    const lx = val > 220 ? x - 52 : x + 3;
    ctx.fillText(label, lx, yLabel);
    ctx.restore();
  }

  if (t1 !== undefined) drawThresholdLine(t1, '#e74c3c', `t1=${t1}`, 14);
  if (t2 !== undefined) drawThresholdLine(t2, '#2980b9', `t2=${t2}`, 28);
}

// ============================================================
//  Crop Selection
// ============================================================

function getCropRect() {
  if (!state.cropStart || !state.cropEnd) return null;
  const x = Math.round(Math.min(state.cropStart.x, state.cropEnd.x));
  const y = Math.round(Math.min(state.cropStart.y, state.cropEnd.y));
  const w = Math.round(Math.abs(state.cropEnd.x - state.cropStart.x));
  const h = Math.round(Math.abs(state.cropEnd.y - state.cropStart.y));
  return { x, y, width: w, height: h };
}

function drawCropOverlay() {
  const overlay = document.getElementById('overlayCanvas');
  const ctx = overlay.getContext('2d');
  ctx.clearRect(0, 0, overlay.width, overlay.height);

  const r = getCropRect();
  if (!r || r.width < 2 || r.height < 2) return;

  ctx.fillStyle = 'rgba(0,0,0,0.42)';
  ctx.fillRect(0, 0, overlay.width, overlay.height);
  ctx.clearRect(r.x, r.y, r.width, r.height);

  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 2;
  ctx.strokeRect(r.x, r.y, r.width, r.height);

  const handleSize = 6;
  ctx.fillStyle = '#fff';
  [[r.x, r.y], [r.x + r.width, r.y], [r.x, r.y + r.height], [r.x + r.width, r.y + r.height]]
    .forEach(([cx, cy]) => ctx.fillRect(cx - handleSize / 2, cy - handleSize / 2, handleSize, handleSize));

  ctx.fillStyle = '#fff';
  ctx.font = '12px sans-serif';
  ctx.fillText(`${r.width} × ${r.height}`, r.x + 4, r.y + 16);
}

function clientToCanvas(overlay, clientX, clientY) {
  const rect = overlay.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(overlay.width, (clientX - rect.left) * (overlay.width / rect.width))),
    y: Math.max(0, Math.min(overlay.height, (clientY - rect.top) * (overlay.height / rect.height))),
  };
}

function initCropSelection() {
  const overlay = document.getElementById('overlayCanvas');

  overlay.addEventListener('mousedown', (e) => {
    state.isDragging = true;
    state.cropStart = clientToCanvas(overlay, e.clientX, e.clientY);
    state.cropEnd = { ...state.cropStart };
  });

  overlay.addEventListener('mousemove', (e) => {
    if (!state.isDragging) return;
    state.cropEnd = clientToCanvas(overlay, e.clientX, e.clientY);
    drawCropOverlay();
  });

  function finishDrag() {
    if (!state.isDragging) return;
    state.isDragging = false;
    const r = getCropRect();
    if (r && r.width > 5 && r.height > 5) {
      state.cropRect = r;
      document.getElementById('applyCropBtn').disabled = false;
    }
  }

  overlay.addEventListener('mouseup', finishDrag);
  overlay.addEventListener('mouseleave', finishDrag);

  // Touch support
  overlay.addEventListener('touchstart', (e) => {
    e.preventDefault();
    const t = e.touches[0];
    state.isDragging = true;
    state.cropStart = clientToCanvas(overlay, t.clientX, t.clientY);
    state.cropEnd = { ...state.cropStart };
  }, { passive: false });

  overlay.addEventListener('touchmove', (e) => {
    e.preventDefault();
    if (!state.isDragging) return;
    const t = e.touches[0];
    state.cropEnd = clientToCanvas(overlay, t.clientX, t.clientY);
    drawCropOverlay();
  }, { passive: false });

  overlay.addEventListener('touchend', (e) => { e.preventDefault(); finishDrag(); }, { passive: false });
}

// ============================================================
//  UI Flow
// ============================================================

function handleImageUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  state.filename = file.name;

  const reader = new FileReader();
  reader.onload = (evt) => {
    const img = new Image();
    img.onload = () => {
      const MAX_DISPLAY_WIDTH = 800, MAX_DISPLAY_HEIGHT = 600;
      let dw = img.width, dh = img.height;
      if (dw > MAX_DISPLAY_WIDTH) { dh = Math.round(dh * MAX_DISPLAY_WIDTH / dw); dw = MAX_DISPLAY_WIDTH; }
      if (dh > MAX_DISPLAY_HEIGHT) { dw = Math.round(dw * MAX_DISPLAY_HEIGHT / dh); dh = MAX_DISPLAY_HEIGHT; }

      const orig = document.getElementById('originalCanvas');
      const ov = document.getElementById('overlayCanvas');

      orig.width = img.width;
      orig.height = img.height;
      ov.width = img.width;
      ov.height = img.height;

      // Scale display size
      orig.style.width = dw + 'px';
      orig.style.height = dh + 'px';
      ov.style.width = dw + 'px';
      ov.style.height = dh + 'px';

      const ctx = orig.getContext('2d');
      ctx.drawImage(img, 0, 0);
      const id = ctx.getImageData(0, 0, img.width, img.height);
      toGrayscale(id);
      ctx.putImageData(id, 0, 0);

      // Reset crop state
      state.cropStart = null;
      state.cropEnd = null;
      state.cropRect = null;
      ov.getContext('2d').clearRect(0, 0, ov.width, ov.height);
      document.getElementById('applyCropBtn').disabled = true;

      document.getElementById('cropArea').classList.remove('hidden');

      // Hide downstream sections when reloading
      ['section-filter', 'section-level', 'section-threshold'].forEach(id => {
        document.getElementById(id).classList.add('hidden');
      });
    };
    img.src = evt.target.result;
  };
  reader.readAsDataURL(file);
}

function applyCropAndFilter() {
  if (!state.cropRect) return;

  const btn = document.getElementById('applyCropBtn');
  btn.disabled = true;
  btn.textContent = '処理中…';

  // Use setTimeout to allow the browser to render the disabled state first
  setTimeout(() => {
    const origCanvas = document.getElementById('originalCanvas');
    const ctx = origCanvas.getContext('2d');
    const { x, y, width, height } = state.cropRect;
    const croppedData = ctx.getImageData(x, y, width, height);

    // Show step 2
    drawImageData(document.getElementById('croppedCanvas'), croppedData);

    const kernelSize = parseInt(document.getElementById('kernelSize').value);
    const filteredData = applyMedianFilter(croppedData, kernelSize);
    state.filteredImageData = filteredData;

    drawImageData(document.getElementById('filteredCanvas'), filteredData);
    document.getElementById('filterStatus').textContent =
      `メディアンフィルタ（${kernelSize}×${kernelSize}）適用済み`;
    document.getElementById('section-filter').classList.remove('hidden');

    // Step 3 – level adjustment
    const rawHist = computeHistogram(filteredData);
    const analysis = analyseHistogram(rawHist);
    let adjustedData;
    const infoEl = document.getElementById('adjustmentInfo');

    if (analysis.skewed) {
      adjustedData = applyLevelAdjustment(filteredData, analysis.minVal, analysis.maxVal);
      infoEl.className = 'info-box warning visible';
      infoEl.textContent =
        `ヒストグラムが偏っています（有効範囲: ${analysis.minVal}–${analysis.maxVal} / 255）。` +
        `レベル調整を自動適用しました。`;
    } else {
      adjustedData = filteredData;
      infoEl.className = 'info-box info visible';
      infoEl.textContent = 'ヒストグラムは十分に分散しています。レベル調整は不要です。';
    }

    state.adjustedImageData = adjustedData;
    state.histogram = computeHistogram(adjustedData);

    drawImageData(document.getElementById('adjustedCanvas'), adjustedData);
    drawHistogram(document.getElementById('histogramCanvas'), state.histogram);
    document.getElementById('section-level').classList.remove('hidden');

    // Step 4 – threshold preview
    updateThresholdPreview();
    document.getElementById('section-threshold').classList.remove('hidden');

    btn.disabled = false;
    btn.textContent = '切り取りとメディアンフィルタを適用';

    document.getElementById('section-filter').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 20);
}

function updateThresholdPreview() {
  if (!state.adjustedImageData || !state.histogram) return;

  const t1 = parseInt(document.getElementById('t1Slider').value);
  const t2 = parseInt(document.getElementById('t2Slider').value);

  // Sync all t1 controls
  document.getElementById('t1Display').textContent = t1;
  document.getElementById('t1Label').textContent = t1;
  document.getElementById('t1Input').value = t1;

  // Sync all t2 controls
  document.getElementById('t2Display').textContent = t2;
  document.getElementById('t2Label').textContent = t2;
  document.getElementById('t2Input').value = t2;

  state.currentT1 = t1;
  state.currentT2 = t2;

  // Histogram with markers
  drawHistogram(document.getElementById('thresholdHistogramCanvas'), state.histogram, t1, t2);

  // Binary images
  const bin1 = applyThreshold(state.adjustedImageData, t1);
  const bin2 = applyThreshold(state.adjustedImageData, t2);

  drawImageData(document.getElementById('binary1Canvas'), bin1);
  drawImageData(document.getElementById('binary2Canvas'), bin2);

  state.currentCount1 = countWhitePixels(bin1);
  state.currentCount2 = countWhitePixels(bin2);

  document.getElementById('whiteCount1').textContent = state.currentCount1.toLocaleString();
  document.getElementById('whiteCount2').textContent = state.currentCount2.toLocaleString();
}

function addToTable() {
  if (state.currentCount1 === null) return;

  const row = {
    filename: state.filename,
    count1: state.currentCount1,
    count2: state.currentCount2,
    t1: state.currentT1,
    t2: state.currentT2,
  };
  state.tableData.push(row);

  const tbody = document.getElementById('tableBody');
  const emptyRow = tbody.querySelector('.empty-row');
  if (emptyRow) emptyRow.remove();

  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>${escapeHtml(row.filename)}</td>
    <td>${row.count1.toLocaleString()}</td>
    <td>${row.count2.toLocaleString()}</td>
  `;
  tbody.appendChild(tr);

  document.getElementById('exportCSVBtn').disabled = false;
  document.getElementById('section-table').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function exportCSV() {
  if (state.tableData.length === 0) return;

  const header = ['ファイル名', '白画素数(t1)', '白画素数(t2)'];
  const rows = state.tableData.map(r => [
    `"${r.filename.replace(/"/g, '""')}"`,
    r.count1,
    r.count2,
  ]);

  const csv = [header, ...rows].map(r => r.join(',')).join('\r\n');
  const bom = '\uFEFF'; // UTF-8 BOM – helps Excel open with correct encoding
  const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'image_analysis_results.csv';
  a.click();
  URL.revokeObjectURL(url);
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ============================================================
//  Event Wiring
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('imageUpload').addEventListener('change', handleImageUpload);
  document.getElementById('applyCropBtn').addEventListener('click', applyCropAndFilter);

  // Threshold sliders ↔ number inputs (bidirectional sync)
  function syncSliderToInput(sliderId, inputId) {
    const slider = document.getElementById(sliderId);
    const input = document.getElementById(inputId);
    slider.addEventListener('input', () => {
      input.value = slider.value;
      updateThresholdPreview();
    });
    input.addEventListener('input', () => {
      const v = Math.max(0, Math.min(255, parseInt(input.value) || 0));
      input.value = v;
      slider.value = v;
      updateThresholdPreview();
    });
  }
  syncSliderToInput('t1Slider', 't1Input');
  syncSliderToInput('t2Slider', 't2Input');

  document.getElementById('addToTableBtn').addEventListener('click', addToTable);
  document.getElementById('exportCSVBtn').addEventListener('click', exportCSV);

  // Attach crop selection once DOM is ready
  initCropSelection();
});
