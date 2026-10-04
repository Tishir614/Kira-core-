"""Запуск локальных моделей.

Текстовые модели (чат / код): GGUF запускается через `llama-server` (llama.cpp) — OpenAI-совместимый API.
Также можно подключить уже запущенный сервер (Ollama, LM Studio, vLLM) как «внешнюю» модель.
У чата и кода — отдельные слоты, поэтому обе шторки работают независимо.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from .config import data_dir
from .registry import Registry

SLOTS = ("chat", "code")


class RuntimeError_(Exception):
    pass


def llama_binary() -> str | None:
    return os.environ.get("LLAMA_SERVER_BIN") or shutil.which("llama-server")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Slot:
    def __init__(self) -> None:
        self.model_id: str | None = None
        self.base_url: str | None = None
        self.model_name: str | None = None
        self.proc: subprocess.Popen[bytes] | None = None
        self.loading = False

    def public(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "loading": self.loading}


class Runtime:
    def __init__(self, registry: Registry) -> None:
        self.registry = registry
        self.slots = {name: Slot() for name in SLOTS}

    def status(self) -> dict[str, Any]:
        return {"llama_server": llama_binary(), "slots": {k: s.public() for k, s in self.slots.items()}}

    async def load(self, slot_name: str, model_id: str, ctx: int = 4096, gpu_layers: int = 0) -> None:
        slot = self.slots.get(slot_name)
        if slot is None:
            raise RuntimeError_("slot: chat | code")
        model = self.registry.get(model_id)
        if model is None:
            raise RuntimeError_("Модель не найдена")
        if model["kind"] == "image":
            raise RuntimeError_("Модель изображений загружается в Студии автоматически")
        if slot.loading:
            raise RuntimeError_("Слот уже загружается")
        self.unload(slot_name)
        slot.loading = True
        try:
            if model.get("format") == "remote":
                slot.base_url, slot.model_name = model["base_url"].rstrip("/"), model.get("remote_model")
            elif model.get("format") == "gguf":
                await self._start_llama(slot, model, ctx, gpu_layers)
            else:
                raise RuntimeError_(f"Формат {model.get('format')!r} не поддерживается для чата. Нужен GGUF.")
            slot.model_id = model_id
        finally:
            slot.loading = False

    async def _start_llama(self, slot: Slot, model: dict[str, Any], ctx: int, gpu_layers: int) -> None:
        binary = llama_binary()
        if not binary:
            raise RuntimeError_("llama-server не найден. Установите llama.cpp (https://github.com/ggml-org/llama.cpp/releases), добавьте в PATH или задайте LLAMA_SERVER_BIN.")
        port = _free_port()
        log = (data_dir() / f"llama-{port}.log").open("wb")
        slot.proc = subprocess.Popen(  # noqa: S603 — аргументы списком, без shell
            [binary, "-m", model["path"], "--host", "127.0.0.1", "--port", str(port), "-c", str(ctx), "-ngl", str(gpu_layers)],
            stdout=log, stderr=subprocess.STDOUT,
        )
        slot.base_url, slot.model_name = f"http://127.0.0.1:{port}/v1", None
        deadline = time.monotonic() + 300
        async with httpx.AsyncClient(timeout=3) as c:
            while time.monotonic() < deadline:
                if slot.proc.poll() is not None:
                    self.unload_proc(slot)
                    raise RuntimeError_(f"llama-server завершился (см. лог {log.name})")
                try:
                    if (await c.get(f"http://127.0.0.1:{port}/health")).status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.5)
        self.unload_proc(slot)
        raise RuntimeError_("Таймаут запуска модели")

    @staticmethod
    def unload_proc(slot: Slot) -> None:
        if slot.proc and slot.proc.poll() is None:
            slot.proc.terminate()
            try:
                slot.proc.wait(10)
            except subprocess.TimeoutExpired:
                slot.proc.kill()
        slot.proc = None

    def unload(self, slot_name: str) -> None:
        slot = self.slots[slot_name]
        self.unload_proc(slot)
        slot.model_id = slot.base_url = slot.model_name = None

    def shutdown(self) -> None:
        for name in SLOTS:
            self.unload(name)

    def endpoint(self, slot_name: str) -> tuple[str, str | None]:
        slot = self.slots.get(slot_name)
        if slot is None or not slot.base_url:
            raise RuntimeError_("Модель не загружена. Откройте «Модели» и нажмите «Загрузить».")
        return slot.base_url, slot.model_name
