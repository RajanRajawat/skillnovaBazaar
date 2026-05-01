from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from ..services.database import get_database


@dataclass(frozen=True)
class User:
    id: str
    name: str
    email: str
    password_hash: str
    created_at: str
    updated_at: str

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "User":
        return cls(
            id=str(document["_id"]),
            name=str(document.get("name") or ""),
            email=str(document.get("email") or ""),
            password_hash=str(document.get("passwordHash") or ""),
            created_at=str(document.get("createdAt") or ""),
            updated_at=str(document.get("updatedAt") or ""),
        )

    def to_public_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


class UserStore:
    def __init__(self) -> None:
        self._collection: Collection | None = None

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            collection = get_database()["users"]
            collection.create_index([("email", ASCENDING)], unique=True)
            self._collection = collection
        return self._collection

    def create(self, name: str, email: str, password_hash: str) -> User:
        now = datetime.now(timezone.utc).isoformat()
        document = {
            "name": name,
            "email": email,
            "passwordHash": password_hash,
            "createdAt": now,
            "updatedAt": now,
        }
        try:
            result = self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise ValueError("An account with this email already exists") from exc
        document["_id"] = result.inserted_id
        return User.from_document(document)

    def find_by_email(self, email: str) -> User | None:
        document = self.collection.find_one({"email": email})
        return User.from_document(document) if document else None

    def update_password(self, email: str, password_hash: str) -> User | None:
        now = datetime.now(timezone.utc).isoformat()
        document = self.collection.find_one_and_update(
            {"email": email},
            {
                "$set": {
                    "passwordHash": password_hash,
                    "updatedAt": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return User.from_document(document) if document else None

    def find_by_id(self, user_id: str) -> User | None:
        try:
            object_id = ObjectId(str(user_id))
        except Exception:
            return None
        document = self.collection.find_one({"_id": object_id})
        return User.from_document(document) if document else None


user_store = UserStore()
