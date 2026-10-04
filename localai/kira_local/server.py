from __future__ import annotations

import os
import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import imagegen
from .config import models_dir, outputs_dir
from .downloader import DownloadError, Downloads
from .registry import KINDS, Registry, slugify
from .runtime import Runtime, RuntimeError_

STATIC = Path(__file__).resolve().parent.parent / "web"


class DownloadReq(BaseModel):
    source: str
    kind: str | None = None
    name: str | None = None
    repo: str | None = None
    files: list[str] | None = None
    urls: list[str] | None = None
    hf_token: str | None = None


class LoadReq(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_id: str
    ctx: int = Field(4096, ge=256, le=131072)
    gpu_layers: int = Field(0, ge=0, le=999)


class ExternalReq(BaseModel):
    name: str
    base_url: str
    remote_model: str | None = None
    kind: str = "chat"
    api: str = "openai"  # для kind=image: openai | a1111


class ChatReq(BaseModel):
    slot: str = "chat"
    messages: list[dict[str, Any]]
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=1, le=65536)


class ImageReq(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_id: str
    prompt: str = Field(min_length=1)
    negative: str = ""
    steps: int = Field(25, ge=1, le=150)
    width: int = Field(512, ge=64, le=2048)
    height: int = Field(512, ge=64, le=2048)
    seed: int | None = None
    guidance: float = Field(7.0, ge=0, le=30)
    count: int = Field(1, ge=1, le=4)


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _hostname(value: str) -> str:
    try:
        return (urlsplit("//" + value).hostname or "").lower()
    except ValueError:
        return ""


def create_app(registry: Registry | None = None, transport: httpx.AsyncBaseTransport | None = None, allow_any_host: bool = False) -> FastAPI:
    registry = registry or Registry()
    downloads = Downloads(registry, transport)
    runtime = Runtime(registry)
    images = imagegen.ImageService()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        runtime.shutdown()

    app = FastAPI(title="Kira Local", lifespan=lifespan)

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Any:
        # Защита от DNS-rebinding и CSRF: сервер без авторизации отвечает только на localhost и только своим страницам.
        if not allow_any_host:
            host = _hostname(request.headers.get("host", ""))
            if host not in LOCAL_HOSTS:
                return JSONResponse({"detail": "Недопустимый Host"}, status_code=403)
            origin = request.headers.get("origin")
            if origin and request.method not in ("GET", "HEAD", "OPTIONS") and _hostname(origin.split("://", 1)[-1]) != host:
                return JSONResponse({"detail": "Чужой Origin"}, status_code=403)
        return await call_next(request)

    def hf_token(explicit: str | None) -> str | None:
        return explicit or os.environ.get("HF_TOKEN")

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return {**runtime.status(), "diffusers": imagegen.available(), "images": imagegen.available() or any(m.get("format") == "remote_image" for m in registry.list()), "platform": "desktop", "disk_free": shutil.disk_usage(models_dir()).free}

    # ----- модели -----
    @app.get("/api/models")
    def list_models() -> list[dict[str, Any]]:
        return registry.list()

    @app.delete("/api/models/{model_id}")
    def delete_model(model_id: str) -> dict[str, bool]:
        for name, slot in runtime.slots.items():
            if slot.model_id == model_id:
                runtime.unload(name)
        if not registry.remove(model_id):
            raise HTTPException(404, "Модель не найдена")
        return {"ok": True}

    @app.post("/api/models/external")
    def add_external(req: ExternalReq) -> dict[str, Any]:
        if req.kind not in ("chat", "code", "image") or req.api not in ("openai", "a1111"):
            raise HTTPException(400, "kind: chat | code | image; api: openai | a1111")
        if not re.match(r"^https?://", req.base_url):
            raise HTTPException(400, "base_url должен начинаться с http(s)://")
        return registry.add({"id": slugify(req.name), "name": req.name, "kind": req.kind, "format": "remote_image" if req.kind == "image" else "remote", "api": req.api, "base_url": req.base_url, "remote_model": req.remote_model, "source": "external"})

    # ----- источники -----
    @app.get("/api/hf/files")
    async def hf_files(repo: str, token: str | None = None) -> list[dict[str, Any]]:
        try:
            return await downloads.hf_files(repo, hf_token(token))
        except DownloadError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/hf/search")
    async def hf_search(q: str = "", gguf: int = 0) -> list[dict[str, Any]]:
        try:
            return await downloads.hf_search(q, bool(gguf))
        except DownloadError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/github/assets")
    async def github_assets(repo: str) -> list[dict[str, Any]]:
        try:
            return await downloads.github_assets(repo)
        except DownloadError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/downloads")
    async def start_download(req: DownloadReq) -> dict[str, Any]:
        if req.kind and req.kind not in KINDS:
            raise HTTPException(400, f"kind: {', '.join(KINDS)}")
        try:
            return downloads.start(source=req.source, kind=req.kind, name=req.name, repo=req.repo, files=req.files, urls=req.urls, token=hf_token(req.hf_token))
        except DownloadError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/downloads")
    def list_downloads() -> list[dict[str, Any]]:
        return list(downloads.jobs.values())

    @app.delete("/api/downloads/{job_id}")
    def cancel_download(job_id: str) -> dict[str, bool]:
        return {"ok": downloads.cancel(job_id)}

    # ----- слоты чата / кода -----
    @app.post("/api/slots/{slot}/load")
    async def load_slot(slot: str, req: LoadReq) -> dict[str, Any]:
        try:
            await runtime.load(slot, req.model_id, req.ctx, req.gpu_layers)
        except RuntimeError_ as exc:
            raise HTTPException(400, str(exc)) from exc
        return runtime.status()

    @app.post("/api/slots/{slot}/unload")
    def unload_slot(slot: str) -> dict[str, Any]:
        if slot not in runtime.slots:
            raise HTTPException(404, "slot")
        runtime.unload(slot)
        return runtime.status()

    @app.post("/api/chat")
    async def chat(req: ChatReq) -> StreamingResponse:
        try:
            base, remote_model = runtime.endpoint(req.slot)
        except RuntimeError_ as exc:
            raise HTTPException(409, str(exc)) from exc
        body: dict[str, Any] = {"messages": req.messages, "temperature": req.temperature, "stream": True}
        if req.max_tokens:
            body["max_tokens"] = req.max_tokens
        if remote_model:
            body["model"] = remote_model

        async def relay() -> AsyncIterator[bytes]:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10)) as c:
                    async with c.stream("POST", f"{base}/chat/completions", json=body) as r:
                        if r.status_code >= 400:
                            detail = (await r.aread()).decode("utf-8", "replace")[:300]
                            yield f'data: {{"error": {_json(detail)}}}\n\n'.encode()
                            return
                        async for chunk in r.aiter_raw():
                            yield chunk
            except httpx.HTTPError as exc:
                yield f'data: {{"error": {_json(str(exc))}}}\n\n'.encode()

        return StreamingResponse(relay(), media_type="text/event-stream")

    # ----- изображения -----
    @app.post("/api/image")
    async def image(req: ImageReq) -> dict[str, Any]:
        model = registry.get(req.model_id)
        if model is None or model["kind"] != "image":
            raise HTTPException(400, "Выберите модель изображений")
        if model.get("format") != "remote_image" and not imagegen.available():
            raise HTTPException(501, "Для локальной генерации: pip install diffusers torch transformers accelerate safetensors — либо подключите внешний сервер (вкладка «Свой сервер»)")
        return images.submit(model, req.model_dump(exclude={"model_id"})).public()

    @app.get("/api/image/{job_id}")
    def image_status(job_id: str) -> dict[str, Any]:
        job = images.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Задача не найдена")
        return job.public()

    @app.delete("/api/image/{job_id}")
    def image_cancel(job_id: str) -> dict[str, bool]:
        job = images.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Задача не найдена")
        job.cancel.set()
        return {"ok": True}

    @app.get("/api/gallery")
    def gallery_list() -> list[dict[str, Any]]:
        return imagegen.gallery()

    @app.delete("/api/gallery/{name}")
    def gallery_delete(name: str) -> dict[str, bool]:
        try:
            return {"ok": imagegen.delete_image(name)}
        except imagegen.ImageError as exc:
            raise HTTPException(400, str(exc)) from exc

    app.mount("/outputs", StaticFiles(directory=outputs_dir()), name="outputs")

    @app.get("/{name}")
    def static_file(name: str) -> FileResponse:
        if not re.fullmatch(r"[a-z0-9_-]+\.(js|css|svg)", name) or not (STATIC / name).is_file():
            raise HTTPException(404, "not found")
        return FileResponse(STATIC / name)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    return app


def _json(text: str) -> str:
    import json

    return json.dumps(text, ensure_ascii=False)
