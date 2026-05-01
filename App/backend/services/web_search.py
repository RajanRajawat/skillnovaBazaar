from __future__ import annotations

import re
from typing import Any

import requests

try:
    from ..config.settings import settings
    from ..models.pattern_definitions import KNOWN_PATTERN_NAMES
except ImportError:
    from config.settings import settings
    from models.pattern_definitions import KNOWN_PATTERN_NAMES


class WebSearchService:
    def identify_pattern_name(self, signature: str) -> str | None:
        query = f"{signature} stock chart pattern technical analysis"
        result = self._serpapi(query) or self._bing(query)
        if not result:
            return None
        candidate = self._extract_pattern_name(result)
        if not candidate:
            return None
        if candidate.lower() in KNOWN_PATTERN_NAMES:
            return candidate
        return candidate

    def _serpapi(self, query: str) -> dict[str, Any] | None:
        if not settings.serpapi_key:
            return None
        params = {"engine": "google", "q": query, "api_key": settings.serpapi_key, "num": 3}
        try:
            response = requests.get("https://serpapi.com/search.json", params=params, timeout=8)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return None
        organic = payload.get("organic_results") or []
        return organic[0] if organic else None

    def _bing(self, query: str) -> dict[str, Any] | None:
        if not settings.bing_search_api_key:
            return None
        headers = {"Ocp-Apim-Subscription-Key": settings.bing_search_api_key}
        params = {"q": query, "count": 3, "mkt": "en-IN"}
        try:
            response = requests.get(settings.bing_search_endpoint, headers=headers, params=params, timeout=8)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return None
        values = ((payload.get("webPages") or {}).get("value") or [])
        return values[0] if values else None

    @staticmethod
    def _extract_pattern_name(result: dict[str, Any]) -> str | None:
        text = " ".join(str(result.get(key, "")) for key in ("title", "name", "snippet"))
        match = re.search(r"([A-Z][A-Za-z -]{2,45}\sPattern)", text)
        if match:
            return " ".join(match.group(1).split())
        compact = re.sub(r"[^A-Za-z ]", " ", text)
        words = compact.split()
        if len(words) >= 2:
            return " ".join(words[: min(4, len(words))]).title()
        return None


web_search_service = WebSearchService()
