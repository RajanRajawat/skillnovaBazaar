from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import quote as url_quote

import numpy as np
import pandas as pd
import requests
import yfinance as yf

try:
    from ..config.settings import settings
except ImportError:
    from config.settings import settings


SEED_PATH = settings.data_dir / "instruments_seed.json"
YFINANCE_CACHE_DIR = settings.data_dir / ".yfinance_cache"

YFINANCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
if hasattr(yf, "set_tz_cache_location"):
    yf.set_tz_cache_location(str(YFINANCE_CACHE_DIR))


@lru_cache(maxsize=1)
def market_request_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


@dataclass(frozen=True)
class Instrument:
    symbol: str
    displaySymbol: str
    name: str
    exchange: str
    segment: str
    type: str
    yahoo: str
    expiry: str | None = None
    strike: float | None = None
    optionType: str | None = None
    underlying: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.__dict__.items()
            if value is not None
        }


class TimedCache:
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time() + self.ttl_seconds, value)


class InstrumentService:
    def __init__(self) -> None:
        self._cache = TimedCache(3600)

    def all(self) -> list[Instrument]:
        cached = self._cache.get("all-instruments")
        if cached:
            return cached

        instruments = self._load_seed()
        if settings.enable_remote_instrument_sync:
            instruments.extend(self._remote_nse_equities())
        instruments.extend(self._generated_derivatives(instruments))
        deduped = self._dedupe(instruments)
        self._cache.set("all-instruments", deduped)
        return deduped

    def search(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        clean = query.strip().lower()
        instruments = self.all()
        if not clean:
            return [item.to_dict() for item in instruments[:limit]]

        scored: list[tuple[int, Instrument]] = []
        for item in instruments:
            haystack = " ".join(
                [
                    item.symbol,
                    item.displaySymbol,
                    item.name,
                    item.exchange,
                    item.segment,
                    item.type,
                    item.expiry or "",
                    str(item.strike or ""),
                    item.optionType or "",
                ]
            ).lower()
            if clean in haystack:
                starts = item.symbol.lower().startswith(clean) or item.displaySymbol.lower().startswith(clean)
                exact = item.symbol.lower() == clean or item.displaySymbol.lower() == clean
                score = 100 if exact else 60 if starts else 20
                if item.type in {"index", "equity"}:
                    score += 10
                scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1].displaySymbol))
        return [item.to_dict() for _, item in scored[:limit]]

    def resolve(self, symbol: str) -> Instrument:
        clean = symbol.strip().upper()
        for item in self.all():
            if clean in {item.symbol.upper(), item.displaySymbol.upper(), item.yahoo.upper()}:
                return item

        if clean.endswith((".NS", ".BO")):
            base = clean.rsplit(".", 1)[0]
            exchange = "NSE" if clean.endswith(".NS") else "BSE"
            return Instrument(base, base, base, exchange, "EQUITY", "equity", clean)

        return Instrument(clean, clean, clean, "NSE", "EQUITY", "equity", f"{clean}.NS")

    def _load_seed(self) -> list[Instrument]:
        raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        return [Instrument(**item) for item in raw]

    def _remote_nse_equities(self) -> list[Instrument]:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {
            "User-Agent": "Mozilla/5.0 SkillNovaBazaar/1.0",
            "Accept": "text/csv,*/*",
        }
        try:
            response = requests.get(url, headers=headers, timeout=8)
            response.raise_for_status()
            rows = []
            for line in response.text.splitlines()[1:]:
                columns = [part.strip().strip('"') for part in line.split(",")]
                if len(columns) < 2:
                    continue
                symbol = columns[0]
                name = columns[1]
                rows.append(
                    Instrument(
                        symbol=symbol,
                        displaySymbol=symbol,
                        name=name,
                        exchange="NSE",
                        segment="EQUITY",
                        type="equity",
                        yahoo=f"{symbol}.NS",
                    )
                )
            return rows
        except requests.RequestException:
            return []

    def _generated_derivatives(self, instruments: list[Instrument]) -> list[Instrument]:
        underlyings = [item for item in instruments if item.type in {"equity", "index"}][:60]
        expiries = self._next_monthly_expiries(3)
        generated: list[Instrument] = []
        for item in underlyings:
            base_price = self._rough_price_anchor(item.symbol)
            step = 50 if base_price < 2000 else 100
            strikes = [round((base_price + offset * step) / step) * step for offset in range(-2, 3)]
            for expiry in expiries:
                generated.append(
                    Instrument(
                        symbol=f"{item.symbol}{expiry.replace('-', '')}FUT",
                        displaySymbol=f"{item.displaySymbol} FUT {expiry}",
                        name=f"{item.name} Futures {expiry}",
                        exchange="NSE",
                        segment="F&O",
                        type="future",
                        yahoo=item.yahoo,
                        expiry=expiry,
                        underlying=item.symbol,
                    )
                )
                for strike in strikes:
                    for option_type in ("CE", "PE"):
                        generated.append(
                            Instrument(
                                symbol=f"{item.symbol}{expiry.replace('-', '')}{int(strike)}{option_type}",
                                displaySymbol=f"{item.displaySymbol} {expiry} {int(strike)} {option_type}",
                                name=f"{item.name} Option {expiry} {int(strike)} {option_type}",
                                exchange="NSE",
                                segment="F&O",
                                type="option",
                                yahoo=item.yahoo,
                                expiry=expiry,
                                strike=float(strike),
                                optionType=option_type,
                                underlying=item.symbol,
                            )
                        )
        return generated

    @staticmethod
    def _next_monthly_expiries(count: int) -> list[str]:
        today = datetime.now(timezone.utc).date()
        expiries: list[str] = []
        month = today.month
        year = today.year
        while len(expiries) < count:
            next_month = month % 12 + 1
            next_year = year + (1 if month == 12 else 0)
            last_day = datetime(next_year, next_month, 1).date() - timedelta(days=1)
            expiry = last_day
            while expiry.weekday() != 3:
                expiry -= timedelta(days=1)
            if expiry >= today:
                expiries.append(expiry.isoformat())
            month = next_month
            year = next_year
        return expiries

    @staticmethod
    def _rough_price_anchor(symbol: str) -> int:
        digest = sum(ord(char) for char in symbol)
        if symbol in {"NIFTY50", "BANKNIFTY", "SENSEX"}:
            return {"NIFTY50": 22500, "BANKNIFTY": 48000, "SENSEX": 74000}[symbol]
        return 250 + digest % 5000

    @staticmethod
    def _dedupe(instruments: list[Instrument]) -> list[Instrument]:
        seen: set[tuple[str, str, str]] = set()
        result: list[Instrument] = []
        for item in instruments:
            key = (item.displaySymbol, item.exchange, item.segment)
            if key not in seen:
                seen.add(key)
                result.append(item)
        result.sort(key=lambda value: (value.type not in {"index", "equity"}, value.exchange, value.displaySymbol))
        return result


class MarketDataService:
    def __init__(self, instrument_service: InstrumentService):
        self.instrument_service = instrument_service
        self._cache = TimedCache(settings.cache_ttl_seconds)

    def history(self, symbol: str, range_name: str = "6mo", interval: str = "1d") -> dict[str, Any]:
        instrument = self.instrument_service.resolve(symbol)
        cache_key = f"history:{instrument.yahoo}:{range_name}:{interval}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        candles, provider = self._fetch_live_market_data(instrument.yahoo, range_name, interval)
        fallback = False
        if not candles:
            candles = self._synthetic_history(instrument.symbol, range_name, interval)
            provider = "deterministic-fallback"
            fallback = True

        payload = {
            "instrument": instrument.to_dict(),
            "provider": provider,
            "isFallback": fallback,
            "range": range_name,
            "interval": interval,
            "candles": candles,
            "quote": self.quote_from_candles(candles),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
        self._cache.set(cache_key, payload)
        return payload

    def quote(self, symbol: str) -> dict[str, Any]:
        history = self.history(symbol, "1mo", "1d")
        return history["quote"] | {"instrument": history["instrument"], "provider": history["provider"]}

    def _fetch_live_market_data(self, yahoo_symbol: str, range_name: str, interval: str) -> tuple[list[dict[str, Any]], str]:
        if settings.market_provider.lower() in {"offline", "deterministic-fallback"}:
            return [], "deterministic-fallback"

        candles = self._fetch_yahoo_chart(yahoo_symbol, range_name, interval)
        if candles:
            return candles, "yahoo-chart"

        candles = self._fetch_yfinance(yahoo_symbol, range_name, interval)
        if candles:
            return candles, "yfinance"

        return [], "yahoo-chart"

    @staticmethod
    def quote_from_candles(candles: list[dict[str, Any]]) -> dict[str, Any]:
        if not candles:
            return {"price": 0, "change": 0, "changePercent": 0, "volume": 0}
        latest = candles[-1]
        previous = candles[-2] if len(candles) > 1 else latest
        price = float(latest["close"])
        change = price - float(previous["close"])
        previous_close = float(previous["close"]) or 1
        return {
            "price": round(price, 2),
            "change": round(change, 2),
            "changePercent": round(change / previous_close * 100, 2),
            "volume": int(latest.get("volume") or 0),
        }

    def _fetch_yfinance(self, yahoo_symbol: str, range_name: str, interval: str) -> list[dict[str, Any]]:
        if settings.market_provider.lower() in {"offline", "deterministic-fallback"}:
            return []
        period = self._normalize_range(range_name, interval)
        try:
            frame = yf.download(
                yahoo_symbol,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=settings.yfinance_timeout,
            )
        except Exception:
            return []
        if frame is None or frame.empty:
            return []
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame = frame.dropna(subset=["Open", "High", "Low", "Close"])
        candles: list[dict[str, Any]] = []
        for index, row in frame.tail(600).iterrows():
            dt = pd.Timestamp(index).to_pydatetime()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            candles.append(
                {
                    "time": int(dt.timestamp()),
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(0 if math.isnan(float(row.get("Volume", 0))) else row.get("Volume", 0)),
                }
            )
        return candles

    def _fetch_yahoo_chart(self, yahoo_symbol: str, range_name: str, interval: str) -> list[dict[str, Any]]:
        period = self._normalize_range(range_name, interval)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{url_quote(yahoo_symbol, safe='')}"
        try:
            response = market_request_session().get(
                url,
                params={
                    "range": period,
                    "interval": interval,
                    "includePrePost": "false",
                    "events": "div,splits",
                },
                headers={"User-Agent": "Mozilla/5.0 SkillNovaBazaar/1.0"},
                timeout=max(settings.yfinance_timeout, 10),
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return []

        result = ((payload.get("chart") or {}).get("result") or [])
        if not result:
            return []

        series = result[0]
        timestamps = series.get("timestamp") or []
        indicators = series.get("indicators") or {}
        quote_data = (indicators.get("quote") or [{}])[0]
        opens = quote_data.get("open") or []
        highs = quote_data.get("high") or []
        lows = quote_data.get("low") or []
        closes = quote_data.get("close") or []
        volumes = quote_data.get("volume") or []

        candles: list[dict[str, Any]] = []
        for index, timestamp in enumerate(timestamps):
            open_value = opens[index] if index < len(opens) else None
            high_value = highs[index] if index < len(highs) else None
            low_value = lows[index] if index < len(lows) else None
            close_value = closes[index] if index < len(closes) else None
            if None in {open_value, high_value, low_value, close_value}:
                continue
            volume_value = volumes[index] if index < len(volumes) else 0
            candles.append(
                {
                    "time": int(timestamp),
                    "open": round(float(open_value), 4),
                    "high": round(float(high_value), 4),
                    "low": round(float(low_value), 4),
                    "close": round(float(close_value), 4),
                    "volume": int(volume_value or 0),
                }
            )
        return candles

    @staticmethod
    def _normalize_range(range_name: str, interval: str) -> str:
        allowed = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"}
        if interval in {"1m", "2m", "5m", "15m", "30m", "60m", "90m"}:
            return range_name if range_name in {"1d", "5d", "1mo", "3mo"} else "1mo"
        return range_name if range_name in allowed else "6mo"

    @staticmethod
    def _synthetic_history(symbol: str, range_name: str, interval: str) -> list[dict[str, Any]]:
        days = {"1d": 80, "5d": 120, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 252, "2y": 504, "5y": 900}.get(range_name, 180)
        if interval in {"1m", "5m", "15m", "30m", "60m"}:
            days = 140
            step_seconds = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "60m": 3600}[interval]
        else:
            step_seconds = 86400
        seed = sum(ord(char) for char in symbol)
        rng = random.Random(seed)
        base = InstrumentService._rough_price_anchor(symbol)
        timestamp = int((datetime.now(timezone.utc) - timedelta(seconds=step_seconds * days)).timestamp())
        candles: list[dict[str, Any]] = []
        price = float(base)
        for index in range(days):
            drift = math.sin(index / 13) * 0.7 + math.sin(index / 37) * 1.4
            shock = rng.uniform(-1.8, 1.8)
            open_price = price
            close = max(1, price * (1 + (drift + shock) / 100))
            high = max(open_price, close) * (1 + rng.uniform(0.001, 0.018))
            low = min(open_price, close) * (1 - rng.uniform(0.001, 0.018))
            volume = int(100000 + rng.random() * 900000 + abs(close - open_price) * 5000)
            candles.append(
                {
                    "time": timestamp + index * step_seconds,
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": volume,
                }
            )
            price = close
        return candles


instrument_service = InstrumentService()
market_data_service = MarketDataService(instrument_service)
