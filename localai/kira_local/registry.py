"""Библиотека установленных моделей (JSON-файл)."""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .config import data_dir, models_dir

KINDS = ("chat", "code", "image")


def guess_kind(name: str, has_model_index: bool = False) -> str:
    low = name.lower()
    if has_model_index or re.search(r"stable-diffusion|sdxl|sd[-_]?[0-9]|flux|diffusion|kandinsky", low):
        return "image"
    if re.search(r"coder|code|starcoder|deepseek-coder|codestral", low):
        return "code"
    return "chat"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-.")[:60] or "model"
    return f"{slug}-{uuid.uuid4().hex[:6]}"


class Registry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or data_dir() / "models.json"
        self._lock = threading.Lock()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text("utf-8"))
        except json.JSONDecodeError:
            return []

    def _write(self, items: list[dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def get(self, model_id: str) -> dict[str, Any] | None:
        return next((m for m in self.list() if m["id"] == model_id), None)

    def add(self, entry: dict[str, Any]) -> dict[str, Any]:
        if entry.get("kind") not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        entry = {**entry, "added": int(time.time())}
        with self._lock:
            items = self._read()
            items.append(entry)
            self._write(items)
        return entry

    def remove(self, model_id: str) -> bool:
        with self._lock:
            items = self._read()
            kept = [m for m in items if m["id"] != model_id]
            if len(kept) == len(items):
                return False
            self._write(kept)
        folder = models_dir() / model_id
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
        return True
