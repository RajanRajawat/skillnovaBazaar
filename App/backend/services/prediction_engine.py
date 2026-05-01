from __future__ import annotations

from typing import Any

import numpy as np


BIAS_SCORE = {"Bullish": 1.0, "Bearish": -1.0, "Neutral": 0.0, "Bilateral": 0.0}
STATUS_WEIGHT = {"completed": 1.0, "forming": 0.72}


class PredictionEngine:
    """Blends pattern signals, price behavior, and news sentiment into one directional view."""

    def predict(
        self,
        candles: list[dict[str, Any]],
        patterns: list[dict[str, Any]],
        news: list[dict[str, Any]],
    ) -> dict[str, Any]:
        technical = self._technical_score(patterns)
        momentum = self._momentum_score(candles)
        sentiment = self._news_score(news)
        validation = self._historical_consistency(candles)

        short_term = self._horizon_prediction(
            candles,
            "Short-term",
            5,
            technical * 0.52 + momentum * 0.2 + sentiment * 0.18 + validation * 0.1,
            len(patterns[:5]),
        )
        long_term = self._horizon_prediction(
            candles,
            "Long-term",
            21,
            technical * 0.4 + momentum * 0.18 + sentiment * 0.12 + validation * 0.3,
            len(patterns[:8]),
        )
        drivers = self._drivers(patterns, news, technical, momentum, sentiment)
        return {
            "direction": short_term["direction"],
            "confidence": short_term["confidence"],
            "score": short_term["score"],
            "range": short_term["range"],
            "shortTerm": short_term,
            "longTerm": long_term,
            "components": {
                "technical": round(float(technical), 3),
                "momentum": round(float(momentum), 3),
                "news": round(float(sentiment), 3),
                "historicalConsistency": round(float(validation), 3),
            },
            "drivers": drivers,
            "method": "Weighted ensemble of recent chart-pattern signals, price momentum, historical consistency, and headline sentiment.",
        }

    def _horizon_prediction(
        self,
        candles: list[dict[str, Any]],
        label: str,
        horizon_bars: int,
        blended: float,
        pattern_count: int,
    ) -> dict[str, Any]:
        if blended > 0.16:
            direction = "Bullish"
        elif blended < -0.16:
            direction = "Bearish"
        else:
            direction = "Neutral"

        confidence = 50 + min(47, abs(blended) * 47 + pattern_count * 2.3)
        if direction == "Neutral":
            confidence = min(confidence, 64)

        return {
            "label": label,
            "direction": direction,
            "confidence": round(confidence, 1),
            "score": round(float(blended), 3),
            "horizonBars": horizon_bars,
            "range": self._prediction_range(candles, blended, horizon_bars),
        }

    def _prediction_range(self, candles: list[dict[str, Any]], blended: float, horizon_bars: int) -> dict[str, Any]:
        if not candles:
            return {
                "lower": 0,
                "upper": 0,
                "midpoint": 0,
                "startTime": None,
                "projectedTime": None,
            }

        latest = candles[-1]
        latest_close = float(latest["close"])
        atr = self._atr(candles)
        realized = self._realized_volatility(candles)
        step_seconds = self._median_step_seconds(candles)

        horizon_scale = float(np.sqrt(max(horizon_bars, 1) / 5))
        base_width = max(atr * 1.65 * horizon_scale, latest_close * realized * horizon_scale, latest_close * 0.008)
        drift = latest_close * blended * (0.018 if horizon_bars <= 5 else 0.045)
        midpoint = latest_close + drift
        lower = max(0.01, midpoint - base_width)
        upper = max(lower + 0.01, midpoint + base_width)
        start_time = int(latest.get("time") or 0) or None
        projected_time = int(start_time + step_seconds * horizon_bars) if start_time else None

        return {
            "lower": round(lower, 4),
            "upper": round(upper, 4),
            "midpoint": round(midpoint, 4),
            "startTime": start_time,
            "projectedTime": projected_time,
        }

    @staticmethod
    def _technical_score(patterns: list[dict[str, Any]]) -> float:
        weighted = 0.0
        total = 0.0
        for index, pattern in enumerate(patterns[:10]):
            bias = BIAS_SCORE.get(pattern.get("bias", "Neutral"), 0.0)
            if bias == 0:
                continue
            recency_weight = 1 / (1 + index * 0.22)
            confidence = float(pattern.get("confidence", 0.55))
            status = STATUS_WEIGHT.get(pattern.get("status", "forming"), 0.72)
            weight = confidence * status * recency_weight
            weighted += bias * weight
            total += weight
        return weighted / total if total else 0.0

    @staticmethod
    def _momentum_score(candles: list[dict[str, Any]]) -> float:
        if len(candles) < 25:
            return 0.0
        close = np.array([float(candle["close"]) for candle in candles], dtype=float)
        short = close[-8:].mean()
        medium = close[-21:].mean()
        long = close[-55:].mean() if len(close) >= 55 else close.mean()
        trend = (short - medium) / medium + (medium - long) / long
        returns = np.diff(close[-21:]) / close[-21:-1]
        consistency = float(np.mean(returns > 0) - np.mean(returns < 0))
        return float(np.clip(trend * 8 + consistency * 0.45, -1, 1))

    @staticmethod
    def _news_score(news: list[dict[str, Any]]) -> float:
        if not news:
            return 0.0
        weighted = 0.0
        total = 0.0
        for index, item in enumerate(news[:8]):
            score = float(item.get("sentimentScore", 0))
            weight = 1 / (1 + index * 0.35)
            weighted += score * weight
            total += weight
        return float(np.clip(weighted / total if total else 0, -1, 1))

    @staticmethod
    def _historical_consistency(candles: list[dict[str, Any]]) -> float:
        if len(candles) < 80:
            return 0.0
        close = np.array([float(candle["close"]) for candle in candles], dtype=float)
        window_returns = []
        for start in range(max(0, len(close) - 160), len(close) - 20, 10):
            before = close[start : start + 10].mean()
            after = close[start + 10 : start + 20].mean()
            if before:
                window_returns.append((after - before) / before)
        if not window_returns:
            return 0.0
        recent = (close[-1] - close[-20]) / close[-20]
        historical_alignment = np.mean([1 if value * recent > 0 else -1 for value in window_returns])
        return float(np.clip(historical_alignment * min(abs(recent) * 6, 1), -1, 1))

    @staticmethod
    def _atr(candles: list[dict[str, Any]], window: int = 14) -> float:
        if len(candles) < 2:
            return 0.0
        high = np.array([float(candle["high"]) for candle in candles], dtype=float)
        low = np.array([float(candle["low"]) for candle in candles], dtype=float)
        close = np.array([float(candle["close"]) for candle in candles], dtype=float)
        high_low = high[1:] - low[1:]
        high_close = np.abs(high[1:] - close[:-1])
        low_close = np.abs(low[1:] - close[:-1])
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        return float(np.mean(tr[-window:])) if len(tr) else 0.0

    @staticmethod
    def _realized_volatility(candles: list[dict[str, Any]]) -> float:
        if len(candles) < 8:
            return 0.012
        close = np.array([float(candle["close"]) for candle in candles[-35:]], dtype=float)
        returns = np.diff(close) / np.maximum(close[:-1], 1e-9)
        if len(returns) == 0:
            return 0.012
        return float(np.clip(np.std(returns), 0.006, 0.08))

    @staticmethod
    def _median_step_seconds(candles: list[dict[str, Any]]) -> int:
        times = [int(candle.get("time") or 0) for candle in candles if candle.get("time")]
        if len(times) < 2:
            return 86400
        diffs = [b - a for a, b in zip(times, times[1:]) if b > a]
        if not diffs:
            return 86400
        return int(np.median(diffs))

    @staticmethod
    def _drivers(
        patterns: list[dict[str, Any]],
        news: list[dict[str, Any]],
        technical: float,
        momentum: float,
        sentiment: float,
    ) -> list[str]:
        drivers: list[str] = []
        for pattern in patterns[:3]:
            drivers.append(f"{pattern['name']} ({round(pattern['confidence'] * 100)}%)")
        if abs(momentum) > 0.2:
            drivers.append("Positive price momentum" if momentum > 0 else "Negative price momentum")
        if abs(sentiment) > 0.15:
            drivers.append("Supportive headlines" if sentiment > 0 else "Pressure from headlines")
        if not drivers and abs(technical) < 0.15:
            drivers.append("Mixed technical and news signals")
        return drivers[:5]


prediction_engine = PredictionEngine()
