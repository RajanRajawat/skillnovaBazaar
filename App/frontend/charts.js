const COLORS = {
  black: "#0a0a0a",
  blueDark: "#0d47a1",
  blue: "#1565c0",
  gold: "#f2c94c",
  white: "#ffffff",
};

export class MarketChart {
  constructor(container) {
    this.container = container;
    this.chart = null;
    this.series = null;
    this.canvas = null;
    this.patternSeries = null;
    this.patternPriceLines = [];
    this.trendlineSeries = [];
    this.predictionSeries = [];
    this.trendlines = [];
    this.prediction = null;
    this.pattern = null;
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
  }

  render(candles, type, trendlines = []) {
    this.candles = type === "heikin-ashi" ? toHeikinAshi(candles) : candles;
    this.type = type;
    this.trendlines = trendlines;
    if (window.LightweightCharts) {
      this.renderLightweight(this.candles, type);
    } else {
      this.renderCanvas(this.candles, type);
    }
  }

  renderLightweight(candles, type) {
    this.container.innerHTML = "";
    this.canvas = null;
    this.patternSeries = null;
    this.patternPriceLines = [];
    this.trendlineSeries = [];
    this.predictionSeries = [];
    this.chart = window.LightweightCharts.createChart(this.container, {
      width: this.container.clientWidth,
      height: this.container.clientHeight,
      layout: { background: { color: COLORS.black }, textColor: COLORS.white },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.08)" },
        horzLines: { color: "rgba(255,255,255,0.08)" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.2)" },
      timeScale: { borderColor: "rgba(255,255,255,0.2)", timeVisible: true },
      crosshair: { mode: 1 },
    });
    this.series = this.createSeries(type);
    this.series.setData(seriesData(candles, type));
    this.renderLightweightTrendlines();
    this.chart.timeScale().fitContent();
  }

  createSeries(type) {
    const lw = window.LightweightCharts;
    const options = {
      upColor: COLORS.blue,
      downColor: COLORS.white,
      borderUpColor: COLORS.blue,
      borderDownColor: COLORS.white,
      wickUpColor: COLORS.blue,
      wickDownColor: COLORS.white,
    };
    if (type === "line") {
      return this.chart.addLineSeries
        ? this.chart.addLineSeries({ color: COLORS.blue, lineWidth: 2 })
        : this.chart.addSeries(lw.LineSeries, { color: COLORS.blue, lineWidth: 2 });
    }
    if (type === "area") {
      const areaOptions = {
        lineColor: COLORS.blue,
        topColor: "rgba(21,101,192,0.42)",
        bottomColor: "rgba(10,10,10,0.1)",
        lineWidth: 2,
      };
      return this.chart.addAreaSeries
        ? this.chart.addAreaSeries(areaOptions)
        : this.chart.addSeries(lw.AreaSeries, areaOptions);
    }
    if (type === "bar") {
      return this.chart.addBarSeries
        ? this.chart.addBarSeries(options)
        : this.chart.addSeries(lw.BarSeries, options);
    }
    return this.chart.addCandlestickSeries
      ? this.chart.addCandlestickSeries(options)
      : this.chart.addSeries(lw.CandlestickSeries, options);
  }

  renderCanvas(candles, type) {
    this.chart = null;
    if (!this.canvas) {
      this.container.innerHTML = "";
      this.canvas = document.createElement("canvas");
      this.container.appendChild(this.canvas);
    }
    const rect = this.container.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    this.canvas.width = Math.floor(rect.width * ratio);
    this.canvas.height = Math.floor(rect.height * ratio);
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
    const ctx = this.canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    ctx.fillStyle = COLORS.black;
    ctx.fillRect(0, 0, rect.width, rect.height);
    drawFallback(ctx, candles, type, rect.width, rect.height, this.pattern, this.trendlines, this.prediction);
  }

  resize() {
    if (this.chart) {
      this.chart.applyOptions({
        width: this.container.clientWidth,
        height: this.container.clientHeight,
      });
    } else if (this.candles) {
      this.renderCanvas(this.candles, this.type);
    }
  }

  showPattern(pattern, prediction = null) {
    this.pattern = pattern;
    this.prediction = prediction;
    if (!this.candles?.length) return;
    if (this.chart) {
      this.renderLightweightPattern(pattern, prediction);
      return;
    }
    this.renderCanvas(this.candles, this.type);
  }

  clearPattern() {
    this.pattern = null;
    this.prediction = null;
    if (this.chart) {
      this.clearLightweightPattern();
      return;
    }
    if (this.candles) {
      this.renderCanvas(this.candles, this.type);
    }
  }

  renderLightweightPattern(pattern, prediction = null) {
    this.clearLightweightPattern();
    const range = patternRange(this.candles, pattern);
    if (!range) return;

    this.patternSeries = this.createPatternSeries();
    this.patternSeries.setData(
      this.candles.slice(range.start, range.end + 1).map((candle) => ({
        time: candle.time,
        value: candle.close,
      }))
    );

    if (this.series?.setMarkers) {
      const start = this.candles[range.start];
      const end = this.candles[range.end];
      this.series.setMarkers([
        {
          time: start.time,
          position: "belowBar",
          color: COLORS.gold,
          shape: "circle",
          text: "Start",
        },
        {
          time: end.time,
          position: pattern.bias === "Bearish" ? "aboveBar" : "belowBar",
          color: COLORS.gold,
          shape: pattern.bias === "Bearish" ? "arrowDown" : "arrowUp",
          text: shortLabel(pattern.name, 24),
        },
      ]);
    }

    Object.entries(pattern.levels || {}).forEach(([name, value]) => {
      const price = Number(value);
      if (!Number.isFinite(price) || !this.series?.createPriceLine) return;
      const priceLine = this.series.createPriceLine({
        price,
        color: COLORS.gold,
        lineWidth: 1,
        lineStyle: window.LightweightCharts?.LineStyle?.Dashed ?? 2,
        axisLabelVisible: true,
        title: labelForLevel(name),
      });
      this.patternPriceLines.push(priceLine);
    });

    const predictionEndTime = this.renderLightweightPredictionCross(prediction);
    const padding = Math.max(4, Math.round((range.end - range.start + 1) * 0.22));
    const from = this.candles[Math.max(0, range.start - padding)].time;
    const to = this.candles[Math.min(this.candles.length - 1, range.end + padding)].time;
    this.chart.timeScale().setVisibleRange({ from, to: predictionEndTime ? Math.max(to, predictionEndTime) : to });
  }

  createPatternSeries() {
    const lw = window.LightweightCharts;
    const options = {
      color: COLORS.gold,
      lineWidth: 3,
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    };
    return this.chart.addLineSeries ? this.chart.addLineSeries(options) : this.chart.addSeries(lw.LineSeries, options);
  }

  renderLightweightTrendlines() {
    if (!this.chart || !this.candles?.length) return;
    this.trendlines.forEach((line, index) => {
      const data = trendlineData(this.candles, line);
      if (!data) return;
      const series = this.createOverlayLineSeries({
        color: trendlineColor(line.id, index),
        lineWidth: 1,
        lineStyle: window.LightweightCharts?.LineStyle?.Dashed ?? 2,
      });
      series.setData(data);
      this.trendlineSeries.push(series);
    });
  }

  renderLightweightPredictionCross(prediction) {
    const cross = predictionCrossData(this.candles, prediction);
    if (!cross) return null;
    cross.lines.forEach((line, index) => {
      const series = this.createOverlayLineSeries({
        color: index === 0 ? "rgba(242, 201, 76, 0.95)" : "rgba(255, 255, 255, 0.82)",
        lineWidth: 2,
        lineStyle: window.LightweightCharts?.LineStyle?.Solid ?? 0,
      });
      series.setData(line);
      this.predictionSeries.push(series);
    });
    return cross.endTime;
  }

  createOverlayLineSeries(options) {
    const lw = window.LightweightCharts;
    const merged = {
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
      ...options,
    };
    return this.chart.addLineSeries ? this.chart.addLineSeries(merged) : this.chart.addSeries(lw.LineSeries, merged);
  }

  clearLightweightPattern() {
    if (this.series?.setMarkers) {
      this.series.setMarkers([]);
    }
    if (this.series?.removePriceLine) {
      this.patternPriceLines.forEach((line) => this.series.removePriceLine(line));
    }
    this.patternPriceLines = [];
    if (this.patternSeries && this.chart?.removeSeries) {
      this.chart.removeSeries(this.patternSeries);
    }
    if (this.chart?.removeSeries) {
      this.predictionSeries.forEach((series) => this.chart.removeSeries(series));
    }
    this.patternSeries = null;
    this.predictionSeries = [];
  }
}

function seriesData(candles, type) {
  if (type === "line" || type === "area") {
    return candles.map((candle) => ({ time: candle.time, value: candle.close }));
  }
  return candles.map((candle) => ({
    time: candle.time,
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
  }));
}

function toHeikinAshi(candles) {
  const result = [];
  let previousOpen = null;
  let previousClose = null;
  for (const candle of candles) {
    const close = (candle.open + candle.high + candle.low + candle.close) / 4;
    const open = previousOpen === null ? (candle.open + candle.close) / 2 : (previousOpen + previousClose) / 2;
    const high = Math.max(candle.high, open, close);
    const low = Math.min(candle.low, open, close);
    result.push({ ...candle, open, high, low, close });
    previousOpen = open;
    previousClose = close;
  }
  return result;
}

function drawFallback(ctx, candles, type, width, height, pattern = null, trendlines = [], prediction = null) {
  if (!candles.length) return;
  const pad = 22;
  const min = Math.min(...candles.map((candle) => candle.low));
  const max = Math.max(...candles.map((candle) => candle.high));
  const scaleY = (value) => height - pad - ((value - min) / Math.max(max - min, 1)) * (height - pad * 2);
  const step = (width - pad * 2) / Math.max(candles.length - 1, 1);

  ctx.strokeStyle = "rgba(255,255,255,0.1)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 6; i += 1) {
    const y = pad + ((height - pad * 2) / 5) * i;
    ctx.beginPath();
    ctx.moveTo(pad, y);
    ctx.lineTo(width - pad, y);
    ctx.stroke();
  }

  if (type === "line" || type === "area") {
    if (type === "area") {
      ctx.fillStyle = "rgba(21,101,192,0.22)";
      ctx.beginPath();
      candles.forEach((candle, index) => {
        const x = pad + step * index;
        const y = scaleY(candle.close);
        if (index === 0) ctx.moveTo(x, height - pad);
        ctx.lineTo(x, y);
      });
      ctx.lineTo(width - pad, height - pad);
      ctx.closePath();
      ctx.fill();
    }
    ctx.strokeStyle = COLORS.blue;
    ctx.lineWidth = 2;
    ctx.beginPath();
    candles.forEach((candle, index) => {
      const x = pad + step * index;
      const y = scaleY(candle.close);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    drawTrendlines(ctx, candles, trendlines, pad, scaleY, step);
    drawPatternOverlay(ctx, candles, pattern, width, height, pad, scaleY, step, prediction);
    return;
  }

  const bodyWidth = Math.max(2, Math.min(9, step * 0.58));
  candles.forEach((candle, index) => {
    const x = pad + step * index;
    const rising = candle.close >= candle.open;
    ctx.strokeStyle = rising ? COLORS.blue : COLORS.white;
    ctx.fillStyle = rising ? COLORS.blue : COLORS.white;
    ctx.beginPath();
    ctx.moveTo(x, scaleY(candle.high));
    ctx.lineTo(x, scaleY(candle.low));
    ctx.stroke();
    if (type === "bar") {
      ctx.beginPath();
      ctx.moveTo(x - bodyWidth, scaleY(candle.open));
      ctx.lineTo(x, scaleY(candle.open));
      ctx.moveTo(x, scaleY(candle.close));
      ctx.lineTo(x + bodyWidth, scaleY(candle.close));
      ctx.stroke();
      return;
    }
    const top = scaleY(Math.max(candle.open, candle.close));
    const bottom = scaleY(Math.min(candle.open, candle.close));
    ctx.fillRect(x - bodyWidth / 2, top, bodyWidth, Math.max(1, bottom - top));
  });
  drawTrendlines(ctx, candles, trendlines, pad, scaleY, step);
  drawPatternOverlay(ctx, candles, pattern, width, height, pad, scaleY, step, prediction);
}

function drawTrendlines(ctx, candles, trendlines, pad, scaleY, step) {
  if (!trendlines?.length) return;
  ctx.save();
  ctx.setLineDash([6, 5]);
  trendlines.forEach((line, index) => {
    const data = trendlineData(candles, line);
    if (!data) return;
    ctx.strokeStyle = trendlineColor(line.id, index);
    ctx.lineWidth = 1;
    ctx.beginPath();
    data.forEach((point, offset) => {
      const candleIndex = timeToIndex(candles, point.time);
      const x = pad + step * candleIndex;
      const y = scaleY(point.value);
      if (offset === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
  ctx.restore();
}

function drawPatternOverlay(ctx, candles, pattern, width, height, pad, scaleY, step, prediction = null) {
  const range = patternRange(candles, pattern);
  if (!range) return;

  const startX = pad + step * range.start;
  const endX = pad + step * range.end;
  ctx.save();
  ctx.fillStyle = "rgba(242, 201, 76, 0.08)";
  ctx.fillRect(Math.min(startX, endX), pad, Math.max(Math.abs(endX - startX), 2), height - pad * 2);

  ctx.strokeStyle = COLORS.gold;
  ctx.lineWidth = 3;
  ctx.beginPath();
  candles.slice(range.start, range.end + 1).forEach((candle, offset) => {
    const x = pad + step * (range.start + offset);
    const y = scaleY(candle.close);
    if (offset === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.setLineDash([5, 5]);
  ctx.lineWidth = 1;
  Object.entries(pattern.levels || {}).forEach(([_name, value]) => {
    const price = Number(value);
    if (!Number.isFinite(price)) return;
    const y = scaleY(price);
    ctx.beginPath();
    ctx.moveTo(pad, y);
    ctx.lineTo(width - pad, y);
    ctx.stroke();
  });
  ctx.setLineDash([]);

  ctx.fillStyle = COLORS.gold;
  ctx.font = "600 12px Inter, system-ui, sans-serif";
  ctx.fillText(shortLabel(pattern.name, 24), Math.max(pad, Math.min(startX, width - pad - 160)), pad + 14);
  drawPredictionCross(ctx, candles, prediction, width, pad, scaleY, step);
  ctx.restore();
}

function drawPredictionCross(ctx, candles, prediction, width, pad, scaleY, step) {
  const cross = predictionCrossData(candles, prediction);
  if (!cross) return;
  const startX = pad + step * Math.max(candles.length - 8, 0);
  const endX = width - pad;
  ctx.save();
  ctx.setLineDash([]);
  cross.lines.forEach((line, index) => {
    ctx.strokeStyle = index === 0 ? "rgba(242, 201, 76, 0.95)" : "rgba(255, 255, 255, 0.82)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(startX, scaleY(line[0].value));
    ctx.lineTo(endX, scaleY(line[1].value));
    ctx.stroke();
  });
  ctx.restore();
}

function trendlineData(candles, line) {
  if (!candles?.length || !line) return null;
  const start = clampIndex(line.startIndex ?? 0, candles.length);
  const end = clampIndex(line.endIndex ?? candles.length - 1, candles.length);
  const startValue = Number(line.startValue);
  const endValue = Number(line.endValue);
  if (!Number.isFinite(startValue) || !Number.isFinite(endValue)) return null;
  return [
    { time: candles[Math.min(start, end)].time, value: startValue },
    { time: candles[Math.max(start, end)].time, value: endValue },
  ];
}

function predictionCrossData(candles, prediction) {
  if (!candles?.length || !prediction) return null;
  const horizon = prediction.longTerm || prediction.shortTerm || prediction;
  const range = horizon.range || prediction.range;
  if (!range) return null;
  const upper = Number(range.upper);
  const lower = Number(range.lower);
  if (!Number.isFinite(upper) || !Number.isFinite(lower) || upper <= lower) return null;

  const latest = candles[candles.length - 1];
  const close = Number(latest.close);
  const band = Math.max((upper - lower) * 0.25, Math.abs(close) * 0.004, 0.01);
  const startTime = Number(range.startTime) || latest.time;
  const endTime = Number(range.projectedTime) || startTime + inferStepSeconds(candles) * Number(horizon.horizonBars || 8);
  const startUpper = close + band;
  const startLower = Math.max(0.01, close - band);
  return {
    endTime,
    lines: [
      [
        { time: startTime, value: startLower },
        { time: endTime, value: upper },
      ],
      [
        { time: startTime, value: startUpper },
        { time: endTime, value: lower },
      ],
    ],
  };
}

function trendlineColor(id, index) {
  const colors = {
    "upper-bottoms": "rgba(255, 255, 255, 0.58)",
    "lower-bottoms": "rgba(21, 101, 192, 0.82)",
    "corresponding-bottoms": "rgba(242, 201, 76, 0.68)",
    "higher-highs": "rgba(255, 255, 255, 0.78)",
    "lower-highs": "rgba(21, 101, 192, 0.62)",
    "swing-high": "rgba(242, 201, 76, 0.9)",
  };
  return colors[id] || [COLORS.white, COLORS.blue, COLORS.gold][index % 3];
}

function timeToIndex(candles, time) {
  const index = candles.findIndex((candle) => candle.time === time);
  return index >= 0 ? index : candles.length - 1;
}

function inferStepSeconds(candles) {
  const diffs = [];
  for (let index = 1; index < candles.length; index += 1) {
    const diff = Number(candles[index].time) - Number(candles[index - 1].time);
    if (diff > 0) diffs.push(diff);
  }
  if (!diffs.length) return 86400;
  diffs.sort((a, b) => a - b);
  return diffs[Math.floor(diffs.length / 2)];
}

function patternRange(candles, pattern) {
  if (!candles?.length || !pattern) return null;
  const start = clampIndex(pattern.startIndex ?? candles.length - 60, candles.length);
  const end = clampIndex(pattern.endIndex ?? candles.length - 1, candles.length);
  return { start: Math.min(start, end), end: Math.max(start, end) };
}

function clampIndex(value, length) {
  const index = Number.isFinite(Number(value)) ? Math.trunc(Number(value)) : 0;
  return Math.max(0, Math.min(length - 1, index));
}

function labelForLevel(name) {
  return String(name || "level")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function shortLabel(value, limit) {
  const text = String(value || "");
  return text.length > limit ? `${text.slice(0, limit - 3)}...` : text;
}
