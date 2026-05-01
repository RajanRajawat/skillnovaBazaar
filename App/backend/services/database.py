from __future__ import annotations

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConfigurationError

from ..config.settings import settings


_client: MongoClient | None = None
_database: Database | None = None


def get_database() -> Database:
    global _client, _database
    if _database is not None:
        return _database

    if not settings.mongo_uri:
        raise RuntimeError("MONGO_URI is not configured")

    _client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)
    try:
        database = _client.get_default_database()
    except ConfigurationError:
        database = None
    if database is None:
        if not settings.mongo_db_name:
            raise RuntimeError("Set MONGO_DB_NAME or include a database name in MONGO_URI")
        database = _client[settings.mongo_db_name]

    _database = database
    return _database
