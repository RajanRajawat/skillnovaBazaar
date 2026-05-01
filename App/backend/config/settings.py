from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_DIR.parent
ROOT_DIR = APP_DIR.parent
FRONTEND_DIR = APP_DIR / "frontend"
DATA_DIR = BACKEND_DIR / "data"
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH, encoding="utf-8-sig")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _list_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values or default


@dataclass(frozen=True)
class Settings:
    root_dir: Path = ROOT_DIR
    app_dir: Path = APP_DIR
    backend_dir: Path = BACKEND_DIR
    frontend_dir: Path = FRONTEND_DIR
    data_dir: Path = DATA_DIR
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = _bool_env("FASTAPI_DEBUG", _bool_env("APP_DEBUG", _bool_env("FLASK_DEBUG", False)))
    cors_allow_origins: tuple[str, ...] = _list_env(
        "CORS_ALLOW_ORIGINS",
        ("http://127.0.0.1:3000", "http://localhost:3000"),
    )
    cors_allow_origin_regex: str = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "")
    mongo_uri: str = os.getenv("MONGO_URI", "").strip()
    mongo_db_name: str = os.getenv("MONGO_DB_NAME", "").strip()
    jwt_secret: str = os.getenv("JWT_SECRET", "").strip()
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256").strip() or "HS256"
    jwt_expiration_hours: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    market_provider: str = os.getenv("MARKET_PROVIDER", "yfinance")
    yfinance_timeout: int = int(os.getenv("YFINANCE_TIMEOUT", "8"))
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "45"))
    enable_remote_instrument_sync: bool = _bool_env("ENABLE_REMOTE_INSTRUMENT_SYNC", True)
    newsapi_key: str = os.getenv("NEWSAPI_KEY") or os.getenv("NEWS_API_KEY", "")
    serpapi_key: str = os.getenv("SERPAPI_KEY", "")
    bing_search_api_key: str = os.getenv("BING_SEARCH_API_KEY", "")
    bing_search_endpoint: str = os.getenv(
        "BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"
    )


settings = Settings()
