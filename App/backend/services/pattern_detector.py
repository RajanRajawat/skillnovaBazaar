from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from ..config.settings import settings
from ..models.pattern_definitions import PATTERN_BY_DETECTOR, PATTERN_DEFINITIONS, PatternDefinition
from ..models.unknown_store import UnknownPatternStore
from .web_search import web_search_service


unknown_pattern_store = UnknownPatternStore(settings.data_dir / "unknown_patterns.json")


@dataclass
class Pivot:
    index: int
    value: float


class MarketContext:
    def __init__(self, candles: list[dict[str, Any]]):
        self.candles = candles
        self.open = np.array([float(c["open"]) for c in candles], dtype=float)
        self.high = np.array([float(c["high"]) for c in candles], dtype=float)
        self.low = np.array([float(c["low"]) for c in candles], dtype=float)
        self.close = np.array([float(c["close"]) for c in candles], dtype=float)
        self.volume = np.array([float(c.get("volume") or 0) for c in candles], dtype=float)
        self.length = len(candles)
        self.high_pivots = self._pivots(self.high, "high")
        self.low_pivots = self._pivots(self.low, "low")
        self.atr = self._atr()

    def recent(self, values: np.ndarray, window: int) -> np.ndarray:
        return values[-min(window, self.length) :]

    def slope(self, values: np.ndarray, window: int) -> float:
        series = self.recent(values, window)
        if len(series) < 3 or np.mean(series) == 0:
            return 0.0
        x = np.arange(len(series), dtype=float)
        slope = np.polyfit(x, series, 1)[0]
        return float((slope * len(series)) / np.mean(series))

    def trend(self, window: int = 30) -> float:
        return self.slope(self.close, window)

    def range_ratio(self, window: int = 30) -> float:
        highs = self.recent(self.high, window)
        lows = self.recent(self.low, window)
        mean = float(np.mean(self.recent(self.close, window))) or 1
        return float((np.max(highs) - np.min(lows)) / mean)

    def last_return(self, window: int) -> float:
        if self.length <= window:
            return 0.0
        start = self.close[-window]
        return float((self.close[-1] - start) / start) if start else 0.0

    def support(self, window: int = 40) -> float:
        return float(np.min(self.recent(self.low, window)))

    def resistance(self, window: int = 40) -> float:
        return float(np.max(self.recent(self.high, window)))

    def avg_volume(self, window: int = 30) -> float:
        recent = self.recent(self.volume, window)
        return float(np.mean(recent)) if len(recent) else 0.0

    def last_body_ratio(self) -> float:
        rng = max(float(self.high[-1] - self.low[-1]), 1e-9)
        return abs(float(self.close[-1] - self.open[-1])) / rng

    def _atr(self, window: int = 14) -> float:
        if self.length < 2:
            return 0.0
        high_low = self.high[1:] - self.low[1:]
        high_close = np.abs(self.high[1:] - self.close[:-1])
        low_close = np.abs(self.low[1:] - self.close[:-1])
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        return float(np.mean(tr[-window:])) if len(tr) else 0.0

    @staticmethod
    def _pivots(values: np.ndarray, mode: str, window: int = 3) -> list[Pivot]:
        pivots: list[Pivot] = []
        for index in range(window, len(values) - window):
            area = values[index - window : index + window + 1]
            center = values[index]
            if mode == "high" and center == np.max(area):
                pivots.append(Pivot(index, float(center)))
            if mode == "low" and center == np.min(area):
                pivots.append(Pivot(index, float(center)))
        filtered: list[Pivot] = []
        for pivot in pivots:
            if not filtered or pivot.index - filtered[-1].index >= window:
                filtered.append(pivot)
            else:
                previous = filtered[-1]
                keep_new = pivot.value > previous.value if mode == "high" else pivot.value < previous.value
                if keep_new:
                    filtered[-1] = pivot
        return filtered


DetectorFn = Callable[[MarketContext, PatternDefinition], dict[str, Any] | None]


class PatternDetector:
    def __init__(self) -> None:
        self.detectors: dict[str, DetectorFn] = {
            "head_shoulders": self._head_shoulders,
            "inverse_head_shoulders": self._inverse_head_shoulders,
            "double_top": self._double_top,
            "double_bottom": self._double_bottom,
            "triple_top": self._triple_top,
            "triple_bottom": self._triple_bottom,
            "ascending_triangle": self._ascending_triangle,
            "descending_triangle": self._descending_triangle,
            "symmetrical_triangle": self._symmetrical_triangle,
            "rising_wedge": self._rising_wedge,
            "falling_wedge": self._falling_wedge,
            "bullish_flag": self._bullish_flag,
            "bearish_flag": self._bearish_flag,
            "bullish_pennant": self._bullish_pennant,
            "bearish_pennant": self._bearish_pennant,
            "bullish_rectangle": self._bullish_rectangle,
            "bearish_rectangle": self._bearish_rectangle,
            "cup_handle": self._cup_handle,
            "rounding_top": self._rounding_top,
            "rounding_bottom": self._rounding_bottom,
            "channel": self._channel,
            "broadening_wedge": self._broadening_wedge,
            "megaphone": self._megaphone,
            "diamond_top": self._diamond_top,
            "diamond_bottom": self._diamond_bottom,
            "bump_run": self._bump_run,
            "island_reversal": self._island_reversal,
            "dead_cat_bounce": self._dead_cat_bounce,
            "parabolic_curve": self._parabolic_curve,
            "v_pattern": self._v_pattern,
            "ascending_staircase": self._ascending_staircase,
            "descending_staircase": self._descending_staircase,
            "tower_top": self._tower_top,
            "tower_bottom": self._tower_bottom,
            "pipe_top": self._pipe_top,
            "pipe_bottom": self._pipe_bottom,
            "scallop": self._scallop,
            "spikes": self._spikes,
            "shakeout": self._shakeout,
            "bull_trap": self._bull_trap,
            "bear_trap": self._bear_trap,
            "kicker": self._kicker,
            "morning_star": self._morning_star,
            "evening_star": self._evening_star,
            "running_correction": self._running_correction,
            "complex_double": self._complex_double,
            "complex_head_shoulders": self._complex_head_shoulders,
            "harmonic": self._harmonic,
            "elliott_wave": self._elliott_wave,
            "three_drives": self._three_drives,
            "bullish_wolfe": self._bullish_wolfe,
            "bearish_wolfe": self._bearish_wolfe,
            "gaps": self._gaps,
            "triple_inside_out": self._triple_inside_out,
            "candlestick": self._candlestick,
        }

    def detect(self, candles: list[dict[str, Any]], chart_type: str = "candlestick") -> list[dict[str, Any]]:
        if len(candles) < 12:
            return []
        working = heikin_ashi(candles) if chart_type == "heikin-ashi" else candles
        context = MarketContext(working)
        detections: list[dict[str, Any]] = []
        for definition in PATTERN_DEFINITIONS:
            detector = self.detectors[definition.detector]
            found = detector(context, definition)
            if found:
                detections.append(found)

        detections.sort(key=lambda item: item["confidence"], reverse=True)
        selected = detections[:14]
        unknown = self._unknown_formation(context, selected)
        if unknown:
            selected.append(unknown)
        selected.sort(key=lambda item: item["confidence"], reverse=True)
        return selected

    def trendlines(self, candles: list[dict[str, Any]], chart_type: str = "candlestick") -> list[dict[str, Any]]:
        if len(candles) < 12:
            return []
        working = heikin_ashi(candles) if chart_type == "heikin-ashi" else candles
        context = MarketContext(working)
        lows = self._bottom_points(context)
        highs = self._top_points(context)

        lines: list[dict[str, Any] | None] = []
        if len(lows) >= 2:
            lines.extend(
                (
                    self._horizontal_bottom_line(
                        "upper-bottoms",
                        "Upper Bottoms",
                        self._higher_lows(lows) or [max(lows[-4:], key=lambda pivot: pivot.value)],
                        context.length,
                        "Higher lows: bottoms forming above previous lows.",
                    ),
                    self._horizontal_bottom_line(
                        "lower-bottoms",
                        "Lower Bottoms",
                        self._lower_lows(lows) or [min(lows[-4:], key=lambda pivot: pivot.value)],
                        context.length,
                        "Lower lows: bottoms forming below previous lows.",
                    ),
                    self._corresponding_bottom_line(lows, context.length),
                )
            )
        if len(highs) >= 2:
            lines.extend(
                (
                    self._horizontal_top_line(
                        "higher-highs",
                        "Higher Highs",
                        self._higher_highs(highs) or [max(highs[-4:], key=lambda pivot: pivot.value)],
                        context.length,
                        "Higher highs: peaks forming above previous highs.",
                    ),
                    self._horizontal_top_line(
                        "lower-highs",
                        "Lower Highs",
                        self._lower_highs(highs) or [min(highs[-4:], key=lambda pivot: pivot.value)],
                        context.length,
                        "Lower highs: peaks failing below previous highs.",
                    ),
                    self._swing_high_line(highs, context.length),
                )
            )
        return [line for line in lines if line]

    def _make(
        self,
        definition: PatternDefinition,
        context: MarketContext,
        score: float,
        status: str,
        reason: str,
        start_index: int | None = None,
        levels: dict[str, float] | None = None,
        bias: str | None = None,
    ) -> dict[str, Any] | None:
        if score < 0.55:
            return None
        start = max(0, start_index if start_index is not None else context.length - 60)
        end = context.length - 1
        return {
            "id": definition.id,
            "name": definition.name,
            "category": definition.category,
            "bias": bias or definition.bias,
            "status": status,
            "confidence": round(min(0.97, max(0.55, score)), 3),
            "startIndex": start,
            "endIndex": end,
            "signal": self._signal_for_bias(bias or definition.bias),
            "reason": reason,
            "levels": levels or {},
            "isUnknown": False,
        }

    @staticmethod
    def _bottom_points(ctx: MarketContext) -> list[Pivot]:
        recent_cutoff = max(0, ctx.length - 160)
        lows = [pivot for pivot in ctx.low_pivots if pivot.index >= recent_cutoff]
        if len(lows) >= 6:
            return lows[-12:]

        segment_size = max(4, ctx.length // 12)
        segmented: list[Pivot] = []
        for start in range(0, ctx.length, segment_size):
            end = min(ctx.length, start + segment_size)
            if end - start < 2:
                continue
            offset = int(np.argmin(ctx.low[start:end]))
            index = start + offset
            segmented.append(Pivot(index, float(ctx.low[index])))

        merged = lows + segmented
        deduped = {pivot.index: pivot for pivot in merged}
        return [deduped[index] for index in sorted(deduped)][-12:]

    @staticmethod
    def _top_points(ctx: MarketContext) -> list[Pivot]:
        recent_cutoff = max(0, ctx.length - 160)
        highs = [pivot for pivot in ctx.high_pivots if pivot.index >= recent_cutoff]
        if len(highs) >= 6:
            return highs[-12:]

        segment_size = max(4, ctx.length // 12)
        segmented: list[Pivot] = []
        for start in range(0, ctx.length, segment_size):
            end = min(ctx.length, start + segment_size)
            if end - start < 2:
                continue
            offset = int(np.argmax(ctx.high[start:end]))
            index = start + offset
            segmented.append(Pivot(index, float(ctx.high[index])))

        merged = highs + segmented
        deduped = {pivot.index: pivot for pivot in merged}
        return [deduped[index] for index in sorted(deduped)][-12:]

    @staticmethod
    def _higher_lows(lows: list[Pivot], threshold: float = 0.002) -> list[Pivot]:
        return [
            current
            for previous, current in zip(lows, lows[1:])
            if current.value > previous.value * (1 + threshold)
        ][-4:]

    @staticmethod
    def _lower_lows(lows: list[Pivot], threshold: float = 0.002) -> list[Pivot]:
        return [
            current
            for previous, current in zip(lows, lows[1:])
            if current.value < previous.value * (1 - threshold)
        ][-4:]

    @staticmethod
    def _higher_highs(highs: list[Pivot], threshold: float = 0.002) -> list[Pivot]:
        return [
            current
            for previous, current in zip(highs, highs[1:])
            if current.value > previous.value * (1 + threshold)
        ][-4:]

    @staticmethod
    def _lower_highs(highs: list[Pivot], threshold: float = 0.002) -> list[Pivot]:
        return [
            current
            for previous, current in zip(highs, highs[1:])
            if current.value < previous.value * (1 - threshold)
        ][-4:]

    @staticmethod
    def _horizontal_bottom_line(
        line_id: str,
        name: str,
        pivots: list[Pivot],
        length: int,
        description: str,
        level: float | None = None,
    ) -> dict[str, Any] | None:
        unique = sorted({pivot.index: pivot for pivot in pivots}.values(), key=lambda pivot: pivot.index)
        if not unique:
            return None

        line_level = float(level if level is not None else unique[-1].value)
        touches = sum(1 for pivot in unique if abs(pivot.value - line_level) <= max(abs(line_level) * 0.04, 1e-9))

        return {
            "id": line_id,
            "name": name,
            "type": "horizontal",
            "description": description,
            "startIndex": 0,
            "endIndex": max(0, length - 1),
            "startValue": round(line_level, 4),
            "endValue": round(line_level, 4),
            "level": round(line_level, 4),
            "touches": touches,
            "points": [{"index": pivot.index, "value": round(pivot.value, 4)} for pivot in unique],
        }

    def _horizontal_top_line(
        self,
        line_id: str,
        name: str,
        pivots: list[Pivot],
        length: int,
        description: str,
        level: float | None = None,
    ) -> dict[str, Any] | None:
        return self._horizontal_bottom_line(line_id, name, pivots, length, description, level)

    def _swing_high_line(self, highs: list[Pivot], length: int) -> dict[str, Any] | None:
        if not highs:
            return None
        return self._horizontal_top_line(
            "swing-high",
            "Swing High",
            [highs[-1]],
            length,
            "Latest valid swing high: a chart peak that acts as resistance.",
        )

    def _corresponding_bottom_line(self, lows: list[Pivot], length: int, tolerance: float = 0.04) -> dict[str, Any] | None:
        cluster = self._equal_low_cluster(lows, tolerance) or self._closest_low_pair(lows)
        if not cluster:
            return None
        level = float(np.mean([pivot.value for pivot in cluster]))
        return self._horizontal_bottom_line(
            "corresponding-bottoms",
            "Corresponding Bottoms",
            cluster,
            length,
            "Equal lows: bottoms clustered within 3% to 4% of each other.",
            level,
        )

    @staticmethod
    def _equal_low_cluster(lows: list[Pivot], tolerance: float) -> list[Pivot] | None:
        best: list[Pivot] = []
        best_score = -1.0
        for anchor in lows:
            cluster = [pivot for pivot in lows if abs(pivot.value - anchor.value) / max(abs(anchor.value), 1e-9) <= tolerance]
            if len(cluster) < 2:
                continue
            values = [pivot.value for pivot in cluster]
            tightness = 1 - spread(values)
            recency = max(pivot.index for pivot in cluster) / max(lows[-1].index, 1)
            score = len(cluster) * 2 + tightness + recency
            if score > best_score:
                best = cluster
                best_score = score
        return best or None

    @staticmethod
    def _closest_low_pair(lows: list[Pivot]) -> list[Pivot] | None:
        if len(lows) < 2:
            return None
        best_pair: tuple[Pivot, Pivot] | None = None
        best_distance = float("inf")
        for index, first in enumerate(lows[:-1]):
            for second in lows[index + 1 :]:
                distance = abs(first.value - second.value) / max(abs(first.value), abs(second.value), 1e-9)
                if distance < best_distance:
                    best_pair = (first, second)
                    best_distance = distance
        return list(best_pair) if best_pair else None

    @staticmethod
    def _signal_for_bias(bias: str) -> str:
        if bias == "Bullish":
            return "Upside pressure"
        if bias == "Bearish":
            return "Downside pressure"
        return "Breakout dependent"

    def _head_shoulders(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-5:]
        lows = ctx.low_pivots[-5:]
        if len(highs) < 3 or len(lows) < 2:
            return None
        a, b, c = highs[-3:]
        shoulders_close = near(a.value, c.value, 0.055)
        head_highest = b.value > a.value * 1.025 and b.value > c.value * 1.025
        neckline = float(np.mean([pivot.value for pivot in lows[-2:]]))
        breakdown_risk = ctx.close[-1] <= neckline * 1.03
        score = 0.38 + 0.22 * shoulders_close + 0.24 * head_highest + 0.12 * breakdown_risk + 0.08 * (ctx.trend(80) > 0)
        return self._make(definition, ctx, score, "completed" if ctx.close[-1] < neckline else "forming", "Three recent highs show a dominant middle peak and neckline pressure.", a.index, {"neckline": round(neckline, 2)})

    def _inverse_head_shoulders(self, ctx: MarketContext, definition: PatternDefinition):
        lows = ctx.low_pivots[-5:]
        highs = ctx.high_pivots[-5:]
        if len(lows) < 3 or len(highs) < 2:
            return None
        a, b, c = lows[-3:]
        shoulders_close = near(a.value, c.value, 0.055)
        head_lowest = b.value < a.value * 0.975 and b.value < c.value * 0.975
        neckline = float(np.mean([pivot.value for pivot in highs[-2:]]))
        breakout_risk = ctx.close[-1] >= neckline * 0.97
        score = 0.38 + 0.22 * shoulders_close + 0.24 * head_lowest + 0.12 * breakout_risk + 0.08 * (ctx.trend(80) < 0)
        return self._make(definition, ctx, score, "completed" if ctx.close[-1] > neckline else "forming", "Three recent lows show a dominant middle trough and neckline pressure.", a.index, {"neckline": round(neckline, 2)})

    def _double_top(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-4:]
        lows = ctx.low_pivots[-4:]
        if len(highs) < 2 or len(lows) < 1:
            return None
        a, b = highs[-2:]
        similarity = near(a.value, b.value, 0.035)
        separated = b.index - a.index >= 5
        neckline = min(p.value for p in lows if a.index < p.index < b.index) if any(a.index < p.index < b.index for p in lows) else ctx.support(35)
        score = 0.42 + 0.25 * similarity + 0.12 * separated + 0.12 * (ctx.trend(80) > 0) + 0.09 * (ctx.close[-1] < neckline * 1.02)
        return self._make(definition, ctx, score, "completed" if ctx.close[-1] < neckline else "forming", "Two similar resistance tests are visible near the recent high.", a.index, {"neckline": round(neckline, 2), "resistance": round(max(a.value, b.value), 2)})

    def _double_bottom(self, ctx: MarketContext, definition: PatternDefinition):
        lows = ctx.low_pivots[-4:]
        highs = ctx.high_pivots[-4:]
        if len(lows) < 2 or len(highs) < 1:
            return None
        a, b = lows[-2:]
        similarity = near(a.value, b.value, 0.035)
        separated = b.index - a.index >= 5
        neckline = max(p.value for p in highs if a.index < p.index < b.index) if any(a.index < p.index < b.index for p in highs) else ctx.resistance(35)
        score = 0.42 + 0.25 * similarity + 0.12 * separated + 0.12 * (ctx.trend(80) < 0) + 0.09 * (ctx.close[-1] > neckline * 0.98)
        return self._make(definition, ctx, score, "completed" if ctx.close[-1] > neckline else "forming", "Two similar support tests are visible near the recent low.", a.index, {"neckline": round(neckline, 2), "support": round(min(a.value, b.value), 2)})

    def _triple_top(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-5:]
        if len(highs) < 3:
            return None
        values = [p.value for p in highs[-3:]]
        flat = spread(values) < 0.04
        score = 0.43 + 0.28 * flat + 0.14 * (ctx.trend(90) > 0) + 0.1 * (ctx.close[-1] < np.mean(values) * 0.98)
        return self._make(definition, ctx, score, "forming", "Three resistance taps are clustered in the same price zone.", highs[-3].index, {"resistance": round(float(np.mean(values)), 2)})

    def _triple_bottom(self, ctx: MarketContext, definition: PatternDefinition):
        lows = ctx.low_pivots[-5:]
        if len(lows) < 3:
            return None
        values = [p.value for p in lows[-3:]]
        flat = spread(values) < 0.04
        score = 0.43 + 0.28 * flat + 0.14 * (ctx.trend(90) < 0) + 0.1 * (ctx.close[-1] > np.mean(values) * 1.02)
        return self._make(definition, ctx, score, "forming", "Three support taps are clustered in the same price zone.", lows[-3].index, {"support": round(float(np.mean(values)), 2)})

    def _ascending_triangle(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-5:]
        lows = ctx.low_pivots[-5:]
        if len(highs) < 2 or len(lows) < 2:
            return None
        high_flat = spread([p.value for p in highs[-3:]]) < 0.035 if len(highs) >= 3 else near(highs[-1].value, highs[-2].value, 0.035)
        low_rising = lows[-1].value > lows[-2].value * 1.01
        score = 0.4 + 0.25 * high_flat + 0.22 * low_rising + 0.08 * (ctx.close[-1] > ctx.close[-5])
        return self._make(definition, ctx, score, "forming", "Resistance is flattening while higher lows press into it.", min(highs[-2].index, lows[-2].index), {"resistance": round(ctx.resistance(45), 2)})

    def _descending_triangle(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-5:]
        lows = ctx.low_pivots[-5:]
        if len(highs) < 2 or len(lows) < 2:
            return None
        low_flat = spread([p.value for p in lows[-3:]]) < 0.035 if len(lows) >= 3 else near(lows[-1].value, lows[-2].value, 0.035)
        high_falling = highs[-1].value < highs[-2].value * 0.99
        score = 0.4 + 0.25 * low_flat + 0.22 * high_falling + 0.08 * (ctx.close[-1] < ctx.close[-5])
        return self._make(definition, ctx, score, "forming", "Support is flattening while lower highs press into it.", min(highs[-2].index, lows[-2].index), {"support": round(ctx.support(45), 2)})

    def _symmetrical_triangle(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-4:]
        lows = ctx.low_pivots[-4:]
        if len(highs) < 2 or len(lows) < 2:
            return None
        contracting = ctx.range_ratio(20) < ctx.range_ratio(60) * 0.8
        score = 0.42 + 0.2 * (highs[-1].value < highs[-2].value) + 0.2 * (lows[-1].value > lows[-2].value) + 0.14 * contracting
        return self._make(definition, ctx, score, "forming", "Highs are falling and lows are rising into a tighter range.", min(highs[-2].index, lows[-2].index))

    def _rising_wedge(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-4:]
        lows = ctx.low_pivots[-4:]
        if len(highs) < 2 or len(lows) < 2:
            return None
        high_slope = highs[-1].value - highs[-2].value
        low_slope = lows[-1].value - lows[-2].value
        narrowing = ctx.range_ratio(18) < ctx.range_ratio(55)
        score = 0.42 + 0.22 * (high_slope > 0) + 0.22 * (low_slope > high_slope * 0.7) + 0.1 * narrowing
        return self._make(definition, ctx, score, "forming", "Both boundaries rise while the recent range narrows.", min(highs[-2].index, lows[-2].index))

    def _falling_wedge(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-4:]
        lows = ctx.low_pivots[-4:]
        if len(highs) < 2 or len(lows) < 2:
            return None
        high_slope = highs[-1].value - highs[-2].value
        low_slope = lows[-1].value - lows[-2].value
        narrowing = ctx.range_ratio(18) < ctx.range_ratio(55)
        score = 0.42 + 0.22 * (high_slope < 0) + 0.22 * (low_slope < 0 and abs(high_slope) > abs(low_slope) * 0.7) + 0.1 * narrowing
        return self._make(definition, ctx, score, "forming", "Both boundaries fall while the recent range narrows.", min(highs[-2].index, lows[-2].index))

    def _bullish_flag(self, ctx: MarketContext, definition: PatternDefinition):
        impulse = ctx.last_return(35) - ctx.last_return(15)
        pullback = ctx.slope(ctx.close, 14) < 0
        compact = ctx.range_ratio(14) < ctx.range_ratio(45)
        score = 0.4 + 0.25 * (impulse > 0.06) + 0.18 * pullback + 0.12 * compact
        return self._make(definition, ctx, score, "forming", "A sharp advance is pausing in a controlled pullback.", ctx.length - 35)

    def _bearish_flag(self, ctx: MarketContext, definition: PatternDefinition):
        impulse = ctx.last_return(35) - ctx.last_return(15)
        bounce = ctx.slope(ctx.close, 14) > 0
        compact = ctx.range_ratio(14) < ctx.range_ratio(45)
        score = 0.4 + 0.25 * (impulse < -0.06) + 0.18 * bounce + 0.12 * compact
        return self._make(definition, ctx, score, "forming", "A sharp decline is pausing in a controlled rebound.", ctx.length - 35)

    def _bullish_pennant(self, ctx: MarketContext, definition: PatternDefinition):
        base = self._symmetrical_triangle(ctx, definition)
        impulse = ctx.last_return(45) > 0.07
        if not base:
            return None
        base["confidence"] = round(min(0.97, base["confidence"] + (0.11 if impulse else -0.06)), 3)
        base["reason"] = "A bullish impulse is followed by a compact converging pause."
        return base if base["confidence"] >= 0.55 else None

    def _bearish_pennant(self, ctx: MarketContext, definition: PatternDefinition):
        base = self._symmetrical_triangle(ctx, definition)
        impulse = ctx.last_return(45) < -0.07
        if not base:
            return None
        base["confidence"] = round(min(0.97, base["confidence"] + (0.11 if impulse else -0.06)), 3)
        base["reason"] = "A bearish impulse is followed by a compact converging pause."
        return base if base["confidence"] >= 0.55 else None

    def _bullish_rectangle(self, ctx: MarketContext, definition: PatternDefinition):
        flat_range = ctx.range_ratio(24) < 0.09
        score = 0.42 + 0.24 * flat_range + 0.19 * (ctx.trend(80) > 0.03) + 0.09 * (ctx.close[-1] > np.mean(ctx.recent(ctx.close, 24)))
        return self._make(definition, ctx, score, "forming", "Price is consolidating sideways after an upward trend.", ctx.length - 40, {"support": round(ctx.support(24), 2), "resistance": round(ctx.resistance(24), 2)})

    def _bearish_rectangle(self, ctx: MarketContext, definition: PatternDefinition):
        flat_range = ctx.range_ratio(24) < 0.09
        score = 0.42 + 0.24 * flat_range + 0.19 * (ctx.trend(80) < -0.03) + 0.09 * (ctx.close[-1] < np.mean(ctx.recent(ctx.close, 24)))
        return self._make(definition, ctx, score, "forming", "Price is consolidating sideways after a downward trend.", ctx.length - 40, {"support": round(ctx.support(24), 2), "resistance": round(ctx.resistance(24), 2)})

    def _cup_handle(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 80:
            return None
        window = ctx.recent(ctx.close, 80)
        left = np.mean(window[:15])
        middle = np.min(window[20:60])
        right = np.mean(window[60:72])
        handle = np.mean(window[-8:])
        cup_depth = (min(left, right) - middle) / max(left, right)
        rim_close = near(left, right, 0.08)
        handle_pullback = handle < right and handle > middle
        score = 0.34 + 0.25 * (cup_depth > 0.08) + 0.2 * rim_close + 0.15 * handle_pullback
        return self._make(definition, ctx, score, "forming", "A rounded recovery is followed by a shallow handle pullback.", ctx.length - 80)

    def _rounding_top(self, ctx: MarketContext, definition: PatternDefinition):
        score = self._curve_score(ctx, bearish=True)
        return self._make(definition, ctx, score, "forming", "Recent closes form a slow topping arc.", ctx.length - 70)

    def _rounding_bottom(self, ctx: MarketContext, definition: PatternDefinition):
        score = self._curve_score(ctx, bearish=False)
        return self._make(definition, ctx, score, "forming", "Recent closes form a slow basing arc.", ctx.length - 70)

    def _channel(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-4:]
        lows = ctx.low_pivots[-4:]
        if len(highs) < 2 or len(lows) < 2:
            return None
        hs = (highs[-1].value - highs[-2].value) / max(highs[-2].value, 1)
        ls = (lows[-1].value - lows[-2].value) / max(lows[-2].value, 1)
        score = 0.42 + 0.32 * (abs(hs - ls) < 0.035) + 0.12 * (ctx.range_ratio(60) > 0.04)
        return self._make(definition, ctx, score, "forming", "Swing highs and lows are moving in roughly parallel tracks.", min(highs[-2].index, lows[-2].index))

    def _broadening_wedge(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-4:]
        lows = ctx.low_pivots[-4:]
        if len(highs) < 2 or len(lows) < 2:
            return None
        diverging = highs[-1].value > highs[-2].value and lows[-1].value < lows[-2].value
        score = 0.42 + 0.28 * diverging + 0.16 * (ctx.range_ratio(20) > ctx.range_ratio(60) * 1.1)
        return self._make(definition, ctx, score, "forming", "Volatility is expanding through higher highs and lower lows.", min(highs[-2].index, lows[-2].index))

    def _megaphone(self, ctx: MarketContext, definition: PatternDefinition):
        found = self._broadening_wedge(ctx, definition)
        if found:
            found["reason"] = "Successively wider swings create a megaphone-like range."
        return found

    def _diamond_top(self, ctx: MarketContext, definition: PatternDefinition):
        score = self._diamond_score(ctx, top=True)
        return self._make(definition, ctx, score, "forming", "The range expanded and then contracted near a recent high.", ctx.length - 70)

    def _diamond_bottom(self, ctx: MarketContext, definition: PatternDefinition):
        score = self._diamond_score(ctx, top=False)
        return self._make(definition, ctx, score, "forming", "The range expanded and then contracted near a recent low.", ctx.length - 70)

    def _bump_run(self, ctx: MarketContext, definition: PatternDefinition):
        orderly = ctx.slope(ctx.close, 80) > 0.04
        acceleration = ctx.slope(ctx.close, 20) > ctx.slope(ctx.close, 80) * 1.8
        loss = ctx.close[-1] < np.mean(ctx.recent(ctx.close, 12))
        score = 0.38 + 0.2 * orderly + 0.26 * acceleration + 0.1 * loss
        return self._make(definition, ctx, score, "forming", "An orderly trend accelerated into a steep bump and is losing short-term support.", ctx.length - 90)

    def _island_reversal(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 8:
            return None
        gap_in = ctx.low[-4] > ctx.high[-5] or ctx.high[-4] < ctx.low[-5]
        gap_out = ctx.low[-1] > ctx.high[-2] or ctx.high[-1] < ctx.low[-2]
        score = 0.38 + 0.3 * gap_in + 0.24 * gap_out + 0.08 * (ctx.range_ratio(8) > ctx.range_ratio(40))
        bias = "Bearish" if ctx.high[-1] < ctx.low[-2] else "Bullish" if ctx.low[-1] > ctx.high[-2] else "Bilateral"
        return self._make(definition, ctx, score, "completed" if gap_in and gap_out else "forming", "Recent gaps isolate a compact price island.", ctx.length - 8, bias=bias)

    def _dead_cat_bounce(self, ctx: MarketContext, definition: PatternDefinition):
        fall = ctx.last_return(30) < -0.12
        bounce = ctx.last_return(8) > 0.025
        weak = ctx.close[-1] < np.mean(ctx.recent(ctx.close, 30))
        score = 0.38 + 0.28 * fall + 0.16 * bounce + 0.12 * weak
        return self._make(definition, ctx, score, "forming", "A heavy decline is showing only a shallow recovery attempt.", ctx.length - 35)

    def _parabolic_curve(self, ctx: MarketContext, definition: PatternDefinition):
        recent = ctx.recent(ctx.close, 45)
        if len(recent) < 20:
            return None
        returns = np.diff(recent) / recent[:-1]
        accel = np.mean(returns[-8:]) > np.mean(returns[:20]) * 1.8
        overextended = ctx.close[-1] > np.mean(recent) + 1.8 * np.std(recent)
        score = 0.38 + 0.28 * (ctx.last_return(45) > 0.18) + 0.2 * accel + 0.08 * overextended
        return self._make(definition, ctx, score, "forming", "The advance is accelerating away from its recent mean.", ctx.length - 45)

    def _v_pattern(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 35:
            return None
        window = ctx.recent(ctx.close, 35)
        low_index = int(np.argmin(window))
        left_drop = (window[low_index] - window[0]) / window[0] if window[0] else 0
        right_rise = (window[-1] - window[low_index]) / window[low_index] if window[low_index] else 0
        score = 0.36 + 0.26 * (left_drop < -0.08) + 0.26 * (right_rise > 0.08) + 0.08 * (8 < low_index < 27)
        return self._make(definition, ctx, score, "completed", "A sharp fall was followed by a sharp recovery.", ctx.length - 35 + low_index)

    def _ascending_staircase(self, ctx: MarketContext, definition: PatternDefinition):
        score = 0.38 + 0.42 * self._stair_score(ctx, bullish=True) + 0.1 * (ctx.trend(70) > 0)
        return self._make(definition, ctx, score, "forming", "Recent pivots are stepping through higher highs and higher lows.", ctx.length - 70)

    def _descending_staircase(self, ctx: MarketContext, definition: PatternDefinition):
        score = 0.38 + 0.42 * self._stair_score(ctx, bullish=False) + 0.1 * (ctx.trend(70) < 0)
        return self._make(definition, ctx, score, "forming", "Recent pivots are stepping through lower highs and lower lows.", ctx.length - 70)

    def _tower_top(self, ctx: MarketContext, definition: PatternDefinition):
        score = 0.36 + 0.28 * self._large_body_run(ctx, bullish=True) + 0.26 * self._large_body_run(ctx, bullish=False, offset=0)
        return self._make(definition, ctx, score, "forming", "Tall bullish candles are being answered by tall bearish candles.", ctx.length - 12)

    def _tower_bottom(self, ctx: MarketContext, definition: PatternDefinition):
        score = 0.36 + 0.28 * self._large_body_run(ctx, bullish=False) + 0.26 * self._large_body_run(ctx, bullish=True, offset=0)
        return self._make(definition, ctx, score, "forming", "Tall bearish candles are being answered by tall bullish candles.", ctx.length - 12)

    def _pipe_top(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 3:
            return None
        big = self._big_candle(ctx, -2) and self._big_candle(ctx, -1)
        reversal = ctx.close[-2] > ctx.open[-2] and ctx.close[-1] < ctx.open[-1]
        score = 0.4 + 0.28 * big + 0.22 * reversal + 0.08 * (ctx.trend(30) > 0)
        return self._make(definition, ctx, score, "completed", "Two adjacent large candles show abrupt topping pressure.", ctx.length - 2)

    def _pipe_bottom(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 3:
            return None
        big = self._big_candle(ctx, -2) and self._big_candle(ctx, -1)
        reversal = ctx.close[-2] < ctx.open[-2] and ctx.close[-1] > ctx.open[-1]
        score = 0.4 + 0.28 * big + 0.22 * reversal + 0.08 * (ctx.trend(30) < 0)
        return self._make(definition, ctx, score, "completed", "Two adjacent large candles show abrupt basing pressure.", ctx.length - 2)

    def _scallop(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 55:
            return None
        window = ctx.recent(ctx.close, 55)
        low_index = int(np.argmin(window))
        shallow = 0.04 < (window[0] - window[low_index]) / window[0] < 0.18 if window[0] else False
        recovery = window[-1] > window[0] * 0.98
        score = 0.38 + 0.24 * shallow + 0.2 * recovery + 0.1 * (ctx.trend(100) > 0)
        return self._make(definition, ctx, score, "forming", "A shallow rounded pullback is recovering toward its prior rim.", ctx.length - 55)

    def _spikes(self, ctx: MarketContext, definition: PatternDefinition):
        candle_range = ctx.high[-1] - ctx.low[-1]
        score = 0.38 + 0.32 * (ctx.atr > 0 and candle_range > ctx.atr * 2.4) + 0.18 * (ctx.last_body_ratio() < 0.45)
        bias = "Bearish" if ctx.close[-1] < ctx.open[-1] else "Bullish"
        return self._make(definition, ctx, score, "completed", "The latest range is unusually large versus ATR.", ctx.length - 1, bias=bias)

    def _shakeout(self, ctx: MarketContext, definition: PatternDefinition):
        support = ctx.support(35)
        breached = ctx.low[-1] < support * 1.002 and ctx.close[-1] > support * 1.015
        volume = ctx.volume[-1] > ctx.avg_volume(30) * 1.15 if ctx.avg_volume(30) else False
        score = 0.4 + 0.34 * breached + 0.14 * volume
        return self._make(definition, ctx, score, "completed", "Price swept below support and closed back above it.", ctx.length - 5, {"support": round(support, 2)})

    def _bull_trap(self, ctx: MarketContext, definition: PatternDefinition):
        resistance = ctx.resistance(30)
        breakout = np.max(ctx.high[-4:-1]) >= resistance * 0.998
        failure = ctx.close[-1] < resistance * 0.985
        score = 0.4 + 0.28 * breakout + 0.22 * failure + 0.08 * (ctx.trend(60) > 0)
        return self._make(definition, ctx, score, "completed", "A resistance breakout attempt failed back into the range.", ctx.length - 6, {"resistance": round(resistance, 2)})

    def _bear_trap(self, ctx: MarketContext, definition: PatternDefinition):
        support = ctx.support(30)
        breakdown = np.min(ctx.low[-4:-1]) <= support * 1.002
        recovery = ctx.close[-1] > support * 1.015
        score = 0.4 + 0.28 * breakdown + 0.22 * recovery + 0.08 * (ctx.trend(60) < 0)
        return self._make(definition, ctx, score, "completed", "A support breakdown attempt failed back into the range.", ctx.length - 6, {"support": round(support, 2)})

    def _kicker(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 3:
            return None
        opposite = (ctx.close[-2] > ctx.open[-2] and ctx.close[-1] < ctx.open[-1]) or (ctx.close[-2] < ctx.open[-2] and ctx.close[-1] > ctx.open[-1])
        gap = ctx.open[-1] > ctx.high[-2] or ctx.open[-1] < ctx.low[-2]
        score = 0.38 + 0.28 * opposite + 0.24 * gap + 0.08 * self._big_candle(ctx, -1)
        bias = "Bullish" if ctx.close[-1] > ctx.open[-1] else "Bearish"
        return self._make(definition, ctx, score, "completed", "A gap and opposite candle show abrupt sentiment reversal.", ctx.length - 2, bias=bias)

    def _morning_star(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 4:
            return None
        first_down = ctx.close[-3] < ctx.open[-3]
        small_middle = abs(ctx.close[-2] - ctx.open[-2]) < (ctx.high[-2] - ctx.low[-2]) * 0.35
        third_up = ctx.close[-1] > ctx.open[-1] and ctx.close[-1] > (ctx.open[-3] + ctx.close[-3]) / 2
        score = 0.38 + 0.2 * first_down + 0.18 * small_middle + 0.26 * third_up
        return self._make(definition, ctx, score, "completed", "A three-candle basing reversal is visible.", ctx.length - 3)

    def _evening_star(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 4:
            return None
        first_up = ctx.close[-3] > ctx.open[-3]
        small_middle = abs(ctx.close[-2] - ctx.open[-2]) < (ctx.high[-2] - ctx.low[-2]) * 0.35
        third_down = ctx.close[-1] < ctx.open[-1] and ctx.close[-1] < (ctx.open[-3] + ctx.close[-3]) / 2
        score = 0.38 + 0.2 * first_up + 0.18 * small_middle + 0.26 * third_down
        return self._make(definition, ctx, score, "completed", "A three-candle topping reversal is visible.", ctx.length - 3)

    def _running_correction(self, ctx: MarketContext, definition: PatternDefinition):
        trend = ctx.trend(90)
        retrace = abs(ctx.last_return(18))
        shallow = retrace < abs(ctx.last_return(60)) * 0.45 if abs(ctx.last_return(60)) > 0.02 else False
        score = 0.4 + 0.24 * (abs(trend) > 0.05) + 0.22 * shallow + 0.08 * (ctx.range_ratio(18) < ctx.range_ratio(60))
        bias = "Bullish" if trend > 0 else "Bearish" if trend < 0 else "Bilateral"
        return self._make(definition, ctx, score, "forming", "The correction remains shallow relative to the dominant trend.", ctx.length - 60, bias=bias)

    def _complex_double(self, ctx: MarketContext, definition: PatternDefinition):
        highs = [p.value for p in ctx.high_pivots[-6:]]
        lows = [p.value for p in ctx.low_pivots[-6:]]
        top_cluster = len(highs) >= 4 and spread(highs[-4:]) < 0.055
        bottom_cluster = len(lows) >= 4 and spread(lows[-4:]) < 0.055
        score = 0.36 + 0.32 * top_cluster + 0.32 * bottom_cluster
        bias = "Bearish" if top_cluster and not bottom_cluster else "Bullish" if bottom_cluster and not top_cluster else "Bilateral"
        return self._make(definition, ctx, score, "forming", "Multiple retests are clustering around the same reversal shelf.", ctx.length - 80, bias=bias)

    def _complex_head_shoulders(self, ctx: MarketContext, definition: PatternDefinition):
        highs = ctx.high_pivots[-7:]
        lows = ctx.low_pivots[-7:]
        if len(highs) < 5 and len(lows) < 5:
            return None
        top = len(highs) >= 5 and highs[-3].value == max(p.value for p in highs[-5:])
        bottom = len(lows) >= 5 and lows[-3].value == min(p.value for p in lows[-5:])
        score = 0.36 + 0.34 * top + 0.34 * bottom + 0.08 * (ctx.range_ratio(45) > 0.06)
        bias = "Bearish" if top else "Bullish" if bottom else "Bilateral"
        return self._make(definition, ctx, score, "forming", "Multiple shoulder-like pivots surround a dominant head pivot.", ctx.length - 90, bias=bias)

    def _harmonic(self, ctx: MarketContext, definition: PatternDefinition):
        pivots = alternating_pivots(ctx)[-5:]
        if len(pivots) < 5:
            return None
        legs = [abs(pivots[i + 1].value - pivots[i].value) for i in range(4)]
        ratios = [legs[i + 1] / legs[i] for i in range(3) if legs[i] > 0]
        fib_like = sum(0.45 <= ratio <= 1.75 for ratio in ratios) / max(len(ratios), 1)
        score = 0.38 + 0.42 * fib_like + 0.08 * (ctx.range_ratio(80) > 0.05)
        return self._make(definition, ctx, score, "forming", "The last five pivots have proportionate swing relationships.", pivots[0].index)

    def _elliott_wave(self, ctx: MarketContext, definition: PatternDefinition):
        pivots = alternating_pivots(ctx)[-6:]
        if len(pivots) < 6:
            return None
        higher = pivots[-1].value > pivots[0].value
        alternating = len({p.index for p in pivots}) == len(pivots)
        impulse = abs(ctx.last_return(80)) > 0.08
        score = 0.38 + 0.24 * alternating + 0.2 * impulse + 0.1 * (ctx.range_ratio(80) > 0.07)
        bias = "Bullish" if higher else "Bearish"
        return self._make(definition, ctx, score, "forming", "Alternating pivots approximate an impulse-and-correction wave count.", pivots[0].index, bias=bias)

    def _three_drives(self, ctx: MarketContext, definition: PatternDefinition):
        pivots = alternating_pivots(ctx)[-7:]
        if len(pivots) < 7:
            return None
        drive_values = [pivots[-5].value, pivots[-3].value, pivots[-1].value]
        rhythmic = spread(drive_values) < 0.08 or is_monotonic(drive_values)
        score = 0.38 + 0.34 * rhythmic + 0.14 * (ctx.range_ratio(80) > 0.06)
        bias = "Bearish" if drive_values[-1] > drive_values[0] else "Bullish"
        return self._make(definition, ctx, score, "forming", "Three measured pushes are visible in the latest swing sequence.", pivots[0].index, bias=bias)

    def _bullish_wolfe(self, ctx: MarketContext, definition: PatternDefinition):
        pivots = alternating_pivots(ctx)[-5:]
        if len(pivots) < 5:
            return None
        falling = pivots[-1].value < pivots[0].value
        wedge = ctx.range_ratio(20) < ctx.range_ratio(70)
        score = 0.38 + 0.28 * falling + 0.22 * wedge + 0.08 * (ctx.close[-1] > ctx.low[-1])
        return self._make(definition, ctx, score, "forming", "A falling five-point wedge is nearing mean-reversion territory.", pivots[0].index)

    def _bearish_wolfe(self, ctx: MarketContext, definition: PatternDefinition):
        pivots = alternating_pivots(ctx)[-5:]
        if len(pivots) < 5:
            return None
        rising = pivots[-1].value > pivots[0].value
        wedge = ctx.range_ratio(20) < ctx.range_ratio(70)
        score = 0.38 + 0.28 * rising + 0.22 * wedge + 0.08 * (ctx.close[-1] < ctx.high[-1])
        return self._make(definition, ctx, score, "forming", "A rising five-point wedge is nearing mean-reversion territory.", pivots[0].index)

    def _gaps(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 2:
            return None
        gap_up = ctx.open[-1] > ctx.high[-2] * 1.003
        gap_down = ctx.open[-1] < ctx.low[-2] * 0.997
        score = 0.38 + 0.42 * (gap_up or gap_down) + 0.08 * (ctx.volume[-1] > ctx.avg_volume(30))
        bias = "Bullish" if gap_up else "Bearish" if gap_down else "Bilateral"
        return self._make(definition, ctx, score, "completed", "The latest open displaced beyond the previous range.", ctx.length - 2, bias=bias)

    def _triple_inside_out(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 5:
            return None
        inside = all(ctx.high[-i] <= ctx.high[-4] and ctx.low[-i] >= ctx.low[-4] for i in (3, 2))
        breakout = ctx.close[-1] > ctx.high[-4] or ctx.close[-1] < ctx.low[-4]
        score = 0.38 + 0.28 * inside + 0.24 * breakout + 0.08 * (ctx.last_body_ratio() > 0.55)
        bias = "Bullish" if ctx.close[-1] > ctx.high[-4] else "Bearish" if ctx.close[-1] < ctx.low[-4] else "Bilateral"
        return self._make(definition, ctx, score, "completed" if breakout else "forming", "Inside-bar compression has released outside the mother candle.", ctx.length - 4, bias=bias)

    def _candlestick(self, ctx: MarketContext, definition: PatternDefinition):
        if ctx.length < 3:
            return None
        engulfing_bull = ctx.close[-2] < ctx.open[-2] and ctx.close[-1] > ctx.open[-1] and ctx.close[-1] > ctx.open[-2] and ctx.open[-1] < ctx.close[-2]
        engulfing_bear = ctx.close[-2] > ctx.open[-2] and ctx.close[-1] < ctx.open[-1] and ctx.close[-1] < ctx.open[-2] and ctx.open[-1] > ctx.close[-2]
        hammer = (ctx.close[-1] - ctx.low[-1]) / max(ctx.high[-1] - ctx.low[-1], 1e-9) > 0.65 and ctx.last_body_ratio() < 0.45
        score = 0.38 + 0.28 * (engulfing_bull or engulfing_bear) + 0.16 * hammer + 0.1 * self._big_candle(ctx, -1)
        bias = "Bullish" if engulfing_bull or (hammer and ctx.trend(30) < 0) else "Bearish" if engulfing_bear else "Bilateral"
        return self._make(definition, ctx, score, "completed", "The latest candles show a recognizable candlestick signal.", ctx.length - 3, bias=bias)

    def _curve_score(self, ctx: MarketContext, bearish: bool) -> float:
        window = ctx.recent(ctx.close, 70)
        if len(window) < 30:
            return 0.0
        x = np.linspace(-1, 1, len(window))
        a, _b, _c = np.polyfit(x, window / np.mean(window), 2)
        curvature = a < -0.03 if bearish else a > 0.03
        location = ctx.trend(100) > 0 if bearish else ctx.trend(100) < 0
        turn = ctx.slope(ctx.close, 12) < 0 if bearish else ctx.slope(ctx.close, 12) > 0
        return 0.38 + 0.3 * curvature + 0.16 * location + 0.1 * turn

    def _diamond_score(self, ctx: MarketContext, top: bool) -> float:
        if ctx.length < 70:
            return 0.0
        early = ctx.range_ratio(70)
        mid_high = np.max(ctx.recent(ctx.high, 45))
        mid_low = np.min(ctx.recent(ctx.low, 45))
        late = ctx.range_ratio(16)
        expanded_then_tight = early > late * 1.3 and (mid_high - mid_low) / max(ctx.close[-1], 1) > late
        location = ctx.close[-1] > np.mean(ctx.recent(ctx.close, 100)) if top else ctx.close[-1] < np.mean(ctx.recent(ctx.close, 100))
        return 0.36 + 0.34 * expanded_then_tight + 0.18 * location

    def _stair_score(self, ctx: MarketContext, bullish: bool) -> float:
        highs = ctx.high_pivots[-4:]
        lows = ctx.low_pivots[-4:]
        if len(highs) < 3 or len(lows) < 3:
            return 0.0
        if bullish:
            checks = [highs[i].value < highs[i + 1].value for i in range(len(highs) - 1)]
            checks += [lows[i].value < lows[i + 1].value for i in range(len(lows) - 1)]
        else:
            checks = [highs[i].value > highs[i + 1].value for i in range(len(highs) - 1)]
            checks += [lows[i].value > lows[i + 1].value for i in range(len(lows) - 1)]
        return sum(checks) / len(checks)

    def _large_body_run(self, ctx: MarketContext, bullish: bool, offset: int = 3) -> float:
        end = ctx.length - offset
        start = max(0, end - 4)
        count = 0
        for index in range(start, end):
            body = abs(ctx.close[index] - ctx.open[index])
            rng = max(ctx.high[index] - ctx.low[index], 1e-9)
            direction = ctx.close[index] > ctx.open[index] if bullish else ctx.close[index] < ctx.open[index]
            if direction and body / rng > 0.58:
                count += 1
        return min(1.0, count / 2)

    def _big_candle(self, ctx: MarketContext, index: int) -> bool:
        rng = ctx.high[index] - ctx.low[index]
        return bool(ctx.atr > 0 and rng > ctx.atr * 1.45)

    def _unknown_formation(self, ctx: MarketContext, known: list[dict[str, Any]]) -> dict[str, Any] | None:
        strong_known = any(item["confidence"] > 0.72 for item in known)
        unusual_range = ctx.atr > 0 and (ctx.high[-1] - ctx.low[-1]) > ctx.atr * 2.2
        pivot_cluster = len(alternating_pivots(ctx)[-8:]) >= 7 and ctx.range_ratio(28) > ctx.range_ratio(90) * 1.15
        if strong_known or not (unusual_range or pivot_cluster):
            return None
        signature = (
            f"unclassified {'wide range' if unusual_range else 'pivot cluster'} "
            f"trend {round(ctx.trend(60), 4)} volatility {round(ctx.range_ratio(28), 4)}"
        )
        discovered_name = web_search_service.identify_pattern_name(signature)
        stored = unknown_pattern_store.register_discovery(signature, discovered_name)
        is_unknown = stored["id"].startswith("unknown-")
        return {
            "id": stored["id"],
            "name": stored["name"],
            "category": "Unknown" if is_unknown else "Discovered",
            "bias": "Bilateral",
            "status": "forming",
            "confidence": 0.61,
            "startIndex": max(0, ctx.length - 30),
            "endIndex": ctx.length - 1,
            "signal": "Breakout dependent",
            "reason": stored.get("signature", signature),
            "levels": {},
            "isUnknown": is_unknown,
        }


def heikin_ashi(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    previous_open = None
    previous_close = None
    for candle in candles:
        close = (float(candle["open"]) + float(candle["high"]) + float(candle["low"]) + float(candle["close"])) / 4
        open_price = (float(candle["open"]) + float(candle["close"])) / 2 if previous_open is None else (previous_open + previous_close) / 2
        high = max(float(candle["high"]), open_price, close)
        low = min(float(candle["low"]), open_price, close)
        result.append({**candle, "open": open_price, "high": high, "low": low, "close": close})
        previous_open = open_price
        previous_close = close
    return result


def near(a: float, b: float, tolerance: float) -> bool:
    base = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / base <= tolerance


def spread(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = float(np.mean(values)) or 1.0
    return float((max(values) - min(values)) / mean)


def is_monotonic(values: list[float]) -> bool:
    return all(values[i] <= values[i + 1] for i in range(len(values) - 1)) or all(
        values[i] >= values[i + 1] for i in range(len(values) - 1)
    )


def alternating_pivots(ctx: MarketContext) -> list[Pivot]:
    combined = [(p.index, "H", p) for p in ctx.high_pivots] + [(p.index, "L", p) for p in ctx.low_pivots]
    combined.sort(key=lambda item: item[0])
    result: list[tuple[str, Pivot]] = []
    for _index, kind, pivot in combined:
        if not result or result[-1][0] != kind:
            result.append((kind, pivot))
        else:
            previous_kind, previous = result[-1]
            if (kind == "H" and pivot.value > previous.value) or (kind == "L" and pivot.value < previous.value):
                result[-1] = (previous_kind, pivot)
    return [pivot for _kind, pivot in result]


pattern_detector = PatternDetector()


def detector_coverage() -> dict[str, bool]:
    return {definition.detector: definition.detector in pattern_detector.detectors for definition in PATTERN_DEFINITIONS}
