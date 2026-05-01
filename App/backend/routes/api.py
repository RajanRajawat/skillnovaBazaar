from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..models.pattern_definitions import all_patterns
from ..services.market_data import instrument_service, market_data_service
from ..services.auth import require_authenticated_user
from ..services.news_service import news_service
from ..services.pattern_detector import detector_coverage, pattern_detector, unknown_pattern_store
from ..services.prediction_engine import prediction_engine


router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_authenticated_user)])


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str | None = None
    range_name: str | None = Field(default=None, alias="range")
    interval: str | None = None
    chart_type: str | None = Field(default=None, alias="chartType")


class RenameUnknownRequest(BaseModel):
    name: str = ""


@router.get("/health")
def health() -> dict[str, Any]:
    coverage = detector_coverage()
    return {
        "ok": True,
        "service": "SkillNova Bazaar",
        "time": datetime.now(timezone.utc).isoformat(),
        "patternDetectors": {
            "total": len(coverage),
            "covered": sum(1 for value in coverage.values() if value),
            "missing": [name for name, present in coverage.items() if not present],
        },
    }


@protected_router.get("/instruments")
def instruments(q: str = Query("", alias="q"), limit: str = Query("25")) -> dict[str, Any]:
    parsed_limit = _int_arg(limit, 25, 1, 100)
    return {"results": instrument_service.search(q, parsed_limit), "query": q}


@protected_router.get("/quote")
def quote(symbol: str = "NIFTY50") -> dict[str, Any]:
    return market_data_service.quote(symbol)


@protected_router.get("/market-data")
def market_data(
    symbol: str = "NIFTY50",
    range_name: str = Query("6mo", alias="range"),
    interval: str = "1d",
) -> dict[str, Any]:
    return market_data_service.history(symbol, range_name, interval)


@protected_router.get("/news")
def news(symbol: str = "NIFTY50", limit: str = Query("8")) -> dict[str, Any]:
    parsed_limit = _int_arg(limit, 8, 1, 20)
    instrument = instrument_service.resolve(symbol).to_dict()
    news_payload = news_service.fetch_with_metadata(instrument["symbol"], instrument.get("name", instrument["symbol"]), parsed_limit)
    return {
        "instrument": instrument,
        "news": news_payload["articles"],
        "newsProvider": news_payload["provider"],
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


@protected_router.get("/patterns")
def patterns() -> dict[str, Any]:
    runtime_patterns = unknown_pattern_store.public_patterns()
    return {
        "patterns": all_patterns() + runtime_patterns,
        "knownCount": len(all_patterns()),
        "runtimeCount": len(runtime_patterns),
    }


@protected_router.post("/analyze")
def analyze(
    payload: AnalyzeRequest | None = Body(default=None),
    symbol: str | None = None,
    range_name: str | None = Query(None, alias="range"),
    interval: str | None = None,
    chart_type: str | None = Query(None, alias="chartType"),
) -> dict[str, Any]:
    body = payload or AnalyzeRequest()
    resolved_symbol = body.symbol or symbol or "NIFTY50"
    resolved_range = body.range_name or range_name or "6mo"
    resolved_interval = body.interval or interval or "1d"
    resolved_chart_type = body.chart_type or chart_type or "candlestick"

    history = market_data_service.history(resolved_symbol, resolved_range, resolved_interval)
    instrument = history["instrument"]
    detected = _rank_detected_patterns(pattern_detector.detect(history["candles"], resolved_chart_type))
    trendlines = pattern_detector.trendlines(history["candles"], resolved_chart_type)
    news_payload = news_service.fetch_with_metadata(instrument["symbol"], instrument.get("name", instrument["symbol"]))
    news = news_payload["articles"]
    prediction = prediction_engine.predict(history["candles"], detected, news)

    runtime_patterns = unknown_pattern_store.public_patterns()
    master_patterns = _prioritized_patterns(all_patterns() + runtime_patterns, detected)
    return {
        "instrument": instrument,
        "provider": history["provider"],
        "isFallback": history["isFallback"],
        "range": resolved_range,
        "interval": resolved_interval,
        "chartType": resolved_chart_type,
        "candles": history["candles"],
        "quote": history["quote"],
        "patterns": detected,
        "masterPatterns": master_patterns,
        "trendlines": trendlines,
        "news": news,
        "newsProvider": news_payload["provider"],
        "prediction": prediction,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


@protected_router.put("/patterns/unknown/{pattern_id}")
def rename_unknown(pattern_id: str, payload: RenameUnknownRequest) -> dict[str, Any]:
    name = str(payload.name).strip()
    try:
        item = unknown_pattern_store.rename_unknown(pattern_id, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"pattern": item, "patterns": all_patterns() + unknown_pattern_store.public_patterns()}


def _rank_detected_patterns(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = [dict(pattern) for pattern in patterns]
    ranked.sort(key=lambda pattern: _validity_score(pattern), reverse=True)
    used: set[int] = set()
    for index, pattern in enumerate(ranked):
        percent = max(1, min(99, round(_validity_score(pattern)) - index))
        while percent in used and percent > 1:
            percent -= 1
        while percent in used and percent < 99:
            percent += 1
        pattern["validPercent"] = percent
        pattern["validityScore"] = round(_validity_score(pattern), 2)
        used.add(percent)
    ranked.sort(key=lambda pattern: (-int(pattern["validPercent"]), -float(pattern.get("confidence") or 0), pattern["name"]))
    return ranked


def _validity_score(pattern: dict[str, Any]) -> float:
    confidence = float(pattern.get("confidence") or 0) * 100
    status_bonus = 2.5 if pattern.get("status") == "completed" else 0
    level_bonus = min(len(pattern.get("levels") or {}) * 1.1, 3.3)
    span = max(1, int(pattern.get("endIndex", 0)) - int(pattern.get("startIndex", 0)))
    span_bonus = 1.5 if 8 <= span <= 120 else 0
    unknown_penalty = 2.0 if pattern.get("isUnknown") else 0.0
    return confidence + status_bonus + level_bonus + span_bonus - unknown_penalty


def _prioritized_patterns(base_patterns: list[dict[str, Any]], detected_patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    detected_by_id = {pattern["id"]: pattern for pattern in detected_patterns}
    enriched: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, pattern in enumerate(base_patterns):
        pattern_id = pattern["id"]
        detected = detected_by_id.get(pattern_id)
        item = dict(pattern)
        item["_sourceOrder"] = index
        item["validForGraph"] = detected is not None
        item["validPercent"] = _valid_percent(detected)
        if detected:
            item.update(detected)
            item["validForGraph"] = True
            item["validPercent"] = _valid_percent(detected)
        enriched.append(item)
        seen.add(pattern_id)

    for detected in detected_patterns:
        if detected["id"] in seen:
            continue
        item = dict(detected)
        item["_sourceOrder"] = len(enriched)
        item["validForGraph"] = True
        item["validPercent"] = _valid_percent(detected)
        enriched.append(item)

    enriched.sort(
        key=lambda item: (
            not item["validForGraph"],
            -int(item.get("validPercent") or 0),
            -float(item.get("confidence") or 0),
            item["_sourceOrder"],
        )
    )
    for item in enriched:
        item.pop("_sourceOrder", None)
    return enriched


def _valid_percent(pattern: dict[str, Any] | None) -> int:
    if not pattern:
        return 0
    if pattern.get("validPercent") is not None:
        return int(pattern["validPercent"])
    return round(float(pattern.get("confidence") or 0) * 100)


def _int_arg(raw: str | int | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw if raw is not None else default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


router.include_router(protected_router)
