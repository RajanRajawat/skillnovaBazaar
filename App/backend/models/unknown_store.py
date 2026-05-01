from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class UnknownPatternStore:
    """Small JSON-backed registry for runtime-discovered and user-renamed patterns."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"unknown": [], "discovered": []})

    def all(self) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            return self._read()

    def public_patterns(self) -> list[dict[str, Any]]:
        data = self.all()
        patterns: list[dict[str, Any]] = []
        for item in data["discovered"]:
            patterns.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "category": "Discovered",
                    "bias": item.get("bias", "Bilateral"),
                    "detector": "web_discovered",
                    "description": item.get("signature", ""),
                    "source": item.get("source", "web-search"),
                }
            )
        for item in data["unknown"]:
            patterns.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "category": "Unknown",
                    "bias": item.get("bias", "Bilateral"),
                    "detector": "unknown",
                    "description": item.get("signature", ""),
                    "isUnknown": True,
                }
            )
        return patterns

    def register_discovery(self, signature: str, discovered_name: str | None) -> dict[str, Any]:
        digest = self._signature_hash(signature)
        with self._lock:
            data = self._read()
            for bucket in ("discovered", "unknown"):
                for item in data[bucket]:
                    if item["signatureHash"] == digest:
                        return item

            now = datetime.now(timezone.utc).isoformat()
            if discovered_name:
                item = {
                    "id": f"discovered-{digest[:10]}",
                    "name": discovered_name.strip(),
                    "signature": signature,
                    "signatureHash": digest,
                    "source": "web-search",
                    "createdAt": now,
                }
                data["discovered"].append(item)
            else:
                next_number = len(data["unknown"]) + 1
                item = {
                    "id": f"unknown-{next_number}",
                    "name": f"Unknown {next_number}",
                    "signature": signature,
                    "signatureHash": digest,
                    "createdAt": now,
                }
                data["unknown"].append(item)
            self._write(data)
            return item

    def rename_unknown(self, pattern_id: str, name: str) -> dict[str, Any]:
        clean_name = " ".join(name.strip().split())
        if not clean_name:
            raise ValueError("Pattern name cannot be empty")
        with self._lock:
            data = self._read()
            for item in data["unknown"]:
                if item["id"] == pattern_id:
                    item["name"] = clean_name
                    item["renamedAt"] = datetime.now(timezone.utc).isoformat()
                    self._write(data)
                    return item
        raise KeyError(f"Unknown pattern {pattern_id} was not found")

    def _read(self) -> dict[str, list[dict[str, Any]]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {"unknown": [], "discovered": []}

    def _write(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _signature_hash(signature: str) -> str:
        return hashlib.sha256(signature.encode("utf-8")).hexdigest()
