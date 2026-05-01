from __future__ import annotations

import calendar
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser
import requests

try:
    from ..config.settings import settings
except ImportError:
    from config.settings import settings


POSITIVE_WORDS = {
    "beats", "beat", "growth", "profit", "surge", "rally", "upgrade", "buy",
    "record", "strong", "wins", "approval", "expands", "higher", "bullish",
}
NEGATIVE_WORDS = {
    "miss", "loss", "falls", "fall", "drops", "downgrade", "sell", "probe",
    "weak", "decline", "lower", "bearish", "default", "fraud", "cuts",
}

BROKEN_LOCAL_PROXY_VALUES = {"http://127.0.0.1:9", "https://127.0.0.1:9"}


class NewsService:
    def fetch(self, symbol: str, company_name: str, limit: int = 8) -> list[dict[str, Any]]:
        return self.fetch_with_metadata(symbol, company_name, limit)["articles"]

    def fetch_with_metadata(self, symbol: str, company_name: str, limit: int = 8) -> dict[str, Any]:
        google_articles = self._fetch_google_rss(symbol, company_name, max(limit, 12))
        newsapi_articles = self._fetch_newsapi(symbol, company_name, max(limit, 12)) if settings.newsapi_key else []

        if google_articles:
            merged = self._dedupe_and_sort([*google_articles, *newsapi_articles], limit)
            provider = "Google News RSS + NewsAPI" if newsapi_articles else "Google News RSS"
            return {"articles": merged, "provider": provider}

        if newsapi_articles:
            return {"articles": self._dedupe_and_sort(newsapi_articles, limit), "provider": "NewsAPI"}

        return {"articles": [], "provider": "News unavailable"}

    def _fetch_newsapi(self, symbol: str, company_name: str, limit: int) -> list[dict[str, Any]]:
        query = f'"{company_name}" OR "{symbol}" stock India market'
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": limit,
            "apiKey": settings.newsapi_key,
        }
        try:
            response = get_url("https://newsapi.org/v2/everything", params=params, timeout=8)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return []
        articles = []
        for item in payload.get("articles", [])[:limit]:
            title = item.get("title") or ""
            sentiment = score_text(title + " " + (item.get("description") or ""))
            articles.append(
                {
                    "title": title,
                    "source": (item.get("source") or {}).get("name", "NewsAPI"),
                    "url": item.get("url"),
                    "publishedAt": normalize_datetime(item.get("publishedAt")),
                    "sentiment": sentiment["label"],
                    "sentimentScore": sentiment["score"],
                }
            )
        return articles

    def _fetch_google_rss(self, symbol: str, company_name: str, limit: int) -> list[dict[str, Any]]:
        query = quote_plus(f"{company_name} {symbol} stock market India")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        try:
            response = get_url(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 SkillNovaBazaar/1.0",
                    "Accept": "application/rss+xml,application/xml,text/xml,*/*",
                },
                timeout=8,
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except (requests.RequestException, Exception):
            return []
        articles = []
        for entry in feed.entries[:limit]:
            title = getattr(entry, "title", "")
            sentiment = score_text(title)
            published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None) or getattr(entry, "published", None)
            articles.append(
                {
                    "title": title,
                    "source": source_name(entry),
                    "url": getattr(entry, "link", ""),
                    "publishedAt": normalize_datetime(published),
                    "sentiment": sentiment["label"],
                    "sentimentScore": sentiment["score"],
                }
            )
        return articles

    @staticmethod
    def _dedupe_and_sort(articles: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for article in articles:
            key = (article.get("url") or article.get("title") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            article["publishedAt"] = normalize_datetime(article.get("publishedAt"))
            result.append(article)
        result.sort(key=lambda item: item["publishedAt"], reverse=True)
        return result[:limit]


def get_url(url: str, **kwargs: Any) -> requests.Response:
    session = requests.Session()
    session.trust_env = not has_broken_local_proxy()
    return session.get(url, **kwargs)


def has_broken_local_proxy() -> bool:
    proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
    return any(settings_value in BROKEN_LOCAL_PROXY_VALUES for settings_value in proxy_values(proxy_keys))


def proxy_values(keys: tuple[str, ...]) -> list[str]:
    import os

    return [os.getenv(key, "").strip().lower().rstrip("/") for key in keys if os.getenv(key)]


def normalize_datetime(value: Any) -> str:
    dt: datetime | None = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (tuple, list)) and len(value) >= 9:
        dt = datetime.fromtimestamp(calendar.timegm(value[:9]), timezone.utc)
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = parsedate_to_datetime(text)
            except (TypeError, ValueError):
                dt = None

    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def source_name(entry: Any) -> str:
    source = getattr(entry, "source", None)
    if isinstance(source, dict):
        return source.get("title") or "Google News"
    title = getattr(source, "title", None)
    return title or "Google News"


def score_text(text: str) -> dict[str, Any]:
    words = {part.strip(".,:;!?()[]{}\"'").lower() for part in text.split()}
    positive = len(words & POSITIVE_WORDS)
    negative = len(words & NEGATIVE_WORDS)
    total = positive + negative
    if total == 0:
        return {"label": "Neutral", "score": 0}
    raw = (positive - negative) / total
    label = "Bullish" if raw > 0.15 else "Bearish" if raw < -0.15 else "Neutral"
    return {"label": label, "score": round(raw, 3)}


news_service = NewsService()
