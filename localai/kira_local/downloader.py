"""Скачивание моделей: Hugging Face, GitHub releases, прямые ссылки.

Поддерживает докачку (Range), прогресс и отмену. Файлы пишутся строго внутри папки модели.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import models_dir
from .registry import Registry, guess_kind, slugify

HF = "https://huggingface.co"
GH_API = "https://api.github.com"
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GH_HOSTS = ("github.com", "githubusercontent.com")


class DownloadError(Exception):
    pass


def safe_relpath(name: str) -> PurePosixPath:
    p = PurePosixPath(name.replace("\\", "/"))
    if p.is_absolute() or not p.parts or any(part in ("..", "") for part in p.parts):
        raise DownloadError(f"Недопустимый путь файла: {name!r}")
    return p


def check_url(url: str, allowed_hosts: tuple[str, ...] | None = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise DownloadError("Разрешены только http(s) ссылки")
    if allowed_hosts and not any(parsed.hostname == h or parsed.hostname.endswith("." + h) for h in allowed_hosts):
        raise DownloadError(f"Хост {parsed.hostname} не разрешён для этого источника")
    return url


class Downloads:
    def __init__(self, registry: Registry, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.registry = registry
        self.transport = transport
        self.jobs: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}

    def client(self, timeout: float | None = 30) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self.transport, timeout=timeout, follow_redirects=True)

    # ---------- каталоги ----------
    async def hf_files(self, repo: str, token: str | None) -> list[dict[str, Any]]:
        if not REPO_RE.match(repo):
            raise DownloadError("Ожидается repo вида owner/name")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with self.client() as c:
            r = await c.get(f"{HF}/api/models/{repo}", params={"blobs": "true"}, headers=headers)
        if r.status_code == 404:
            raise DownloadError("Репозиторий не найден (или нужен токен)")
        r.raise_for_status()
        return [{"name": s["rfilename"], "size": s.get("size") or 0} for s in r.json().get("siblings", [])]

    async def hf_search(self, query: str, gguf_only: bool) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"search": query, "sort": "downloads", "direction": -1, "limit": 20}
        if gguf_only:
            params["filter"] = "gguf"
        async with self.client() as c:
            r = await c.get(f"{HF}/api/models", params=params)
        r.raise_for_status()
        return [{"id": m.get("id") or m.get("modelId"), "downloads": m.get("downloads", 0), "likes": m.get("likes", 0), "task": m.get("pipeline_tag", "")} for m in r.json()]

    async def github_assets(self, repo: str) -> list[dict[str, Any]]:
        if not REPO_RE.match(repo):
            raise DownloadError("Ожидается repo вида owner/name")
        async with self.client() as c:
            r = await c.get(f"{GH_API}/repos/{repo}/releases", params={"per_page": 5})
        if r.status_code == 404:
            raise DownloadError("Репозиторий или релизы не найдены")
        r.raise_for_status()
        return [
            {"name": a["name"], "size": a.get("size") or 0, "url": a["browser_download_url"], "tag": rel.get("tag_name")}
            for rel in r.json()
            for a in rel.get("assets", [])
        ]

    # ---------- задачи ----------
    def start(self, *, source: str, kind: str | None, name: str | None, repo: str | None, files: list[str] | None, urls: list[str] | None, token: str | None) -> dict[str, Any]:
        if source == "hf":
            if not repo or not REPO_RE.match(repo) or not files:
                raise DownloadError("Для Hugging Face нужны repo и список файлов")
            items = [(f"{HF}/{repo}/resolve/main/{safe_relpath(f)}", safe_relpath(f)) for f in files]
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            title = name or repo.split("/")[-1]
            has_index = any(f.endswith("model_index.json") for f in files)
        elif source in ("github", "url"):
            if not urls:
                raise DownloadError("Нужна хотя бы одна ссылка")
            hosts = GH_HOSTS if source == "github" else None
            items = []
            for u in urls:
                check_url(u, hosts)
                fname = Path(urlparse(u).path).name
                items.append((u, safe_relpath(fname)))
            headers = {}
            title = name or (repo.split("/")[-1] if repo else Path(items[0][1]).stem)
            has_index = False
        else:
            raise DownloadError("source: hf | github | url")

        chosen_kind = kind or guess_kind(title + " " + " ".join(str(p) for _, p in items), has_index)
        job_id = uuid.uuid4().hex[:10]
        model_id = slugify(title)
        job = {
            "id": job_id, "model_id": model_id, "name": title, "kind": chosen_kind, "source": source, "status": "queued", "error": None,
            "files": [{"name": str(p), "done": 0, "total": 0} for _, p in items], "done": 0, "total": 0,
        }
        self.jobs[job_id] = job
        self.tasks[job_id] = asyncio.create_task(self._run(job, items, headers))
        return job

    def cancel(self, job_id: str) -> bool:
        task = self.tasks.get(job_id)
        if not task or task.done():
            return False
        task.cancel()
        return True

    async def _run(self, job: dict[str, Any], items: list[tuple[str, PurePosixPath]], headers: dict[str, str]) -> None:
        folder = models_dir() / job["model_id"]
        job["status"] = "downloading"
        try:
            async with self.client(timeout=None) as c:
                for i, (url, rel) in enumerate(items):
                    dest = folder.joinpath(*rel.parts)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    await self._fetch(c, url, dest, headers, job, job["files"][i])
            main = self._main_path(folder, [r for _, r in items])
            self.registry.add({
                "id": job["model_id"], "name": job["name"], "kind": job["kind"],
                "format": "diffusers" if (folder / "model_index.json").exists() else main.suffix.lstrip(".").lower() or "file",
                "path": str(main), "source": job["source"], "size": job["total"],
            })
            job["status"] = "done"
        except asyncio.CancelledError:
            job["status"] = "cancelled"
            raise
        except Exception as exc:  # noqa: BLE001 — показываем пользователю любую причину
            job["status"], job["error"] = "error", str(exc) or exc.__class__.__name__

    @staticmethod
    def _main_path(folder: Path, rels: list[PurePosixPath]) -> Path:
        if (folder / "model_index.json").exists():
            return folder
        for ext in (".gguf", ".safetensors", ".ckpt", ".bin"):
            for rel in rels:
                if rel.suffix.lower() == ext:
                    return folder.joinpath(*rel.parts)
        return folder.joinpath(*rels[0].parts)

    async def _fetch(self, c: httpx.AsyncClient, url: str, dest: Path, headers: dict[str, str], job: dict[str, Any], f: dict[str, Any]) -> None:
        part = dest.with_name(dest.name + ".part")
        start = part.stat().st_size if part.exists() else 0
        h = dict(headers)
        if start:
            h["Range"] = f"bytes={start}-"
        async with c.stream("GET", url, headers=h) as r:
            if r.status_code == 416:  # докачивать нечего
                part.replace(dest)
                f["done"] = f["total"] = dest.stat().st_size
                return
            if r.status_code in (401, 403):
                raise DownloadError("Доступ запрещён — нужен токен Hugging Face (gated-модель)")
            r.raise_for_status()
            if start and r.status_code != 206:
                start = 0
            length = int(r.headers.get("content-length", 0))
            f["total"] = start + length
            job["total"] = sum(x["total"] for x in job["files"])
            with part.open("ab" if start else "wb") as out:
                f["done"] = start
                async for chunk in r.aiter_bytes(1 << 20):
                    out.write(chunk)
                    f["done"] += len(chunk)
                    job["done"] = sum(x["done"] for x in job["files"])
        part.replace(dest)
