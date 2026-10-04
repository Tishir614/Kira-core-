"""Генерация изображений: локально через diffusers (необязательно) или через внешний сервер
(AUTOMATIC1111 / Forge / SD.Next `/sdapi/v1/txt2img`, либо OpenAI-совместимый `/v1/images/generations`).

Генерация идёт в фоне: у задачи есть прогресс по шагам, отмена, несколько картинок за раз,
а каждая картинка сохраняется вместе с параметрами (галерея).
"""

from __future__ import annotations

import base64
import json
import random
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

from .config import outputs_dir

NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.png$")


class ImageError(Exception):
    pass


def available() -> bool:
    try:
        import diffusers  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


# ---------- галерея ----------
def save_image(png: bytes, meta: dict[str, Any]) -> dict[str, Any]:
    name = f"{int(time.time())}-{uuid.uuid4().hex[:6]}.png"
    out = outputs_dir()
    (out / name).write_bytes(png)
    meta = {**meta, "name": name, "url": f"/outputs/{name}", "created": int(time.time())}
    (out / (name[:-4] + ".json")).write_text(json.dumps(meta, ensure_ascii=False), "utf-8")
    return meta


def gallery(limit: int = 100) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for p in sorted(outputs_dir().glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        side = p.with_suffix(".json")
        try:
            meta = json.loads(side.read_text("utf-8")) if side.exists() else {}
        except json.JSONDecodeError:
            meta = {}
        items.append({**meta, "name": p.name, "url": f"/outputs/{p.name}"})
    return items


def delete_image(name: str) -> bool:
    if not NAME_RE.match(name):
        raise ImageError("Недопустимое имя файла")
    p = outputs_dir() / name
    if not p.exists():
        return False
    p.unlink()
    p.with_suffix(".json").unlink(missing_ok=True)
    return True


# ---------- задачи ----------
class Job:
    def __init__(self, params: dict[str, Any]) -> None:
        self.id = uuid.uuid4().hex[:10]
        self.params = params
        self.status = "queued"
        self.step = 0
        self.total = params["steps"] * params["count"]
        self.images: list[dict[str, Any]] = []
        self.error: str | None = None
        self.cancel = threading.Event()

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status, "step": self.step, "total": self.total, "images": self.images, "error": self.error}


class ImageService:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self._pool = ThreadPoolExecutor(max_workers=1)  # одна GPU — одна задача
        self._pipe: Any = None
        self._loaded: str | None = None

    def submit(self, model: dict[str, Any], params: dict[str, Any]) -> Job:
        if params.get("seed") is None:
            params["seed"] = random.randint(0, 2**31 - 1)
        job = Job(params)
        self.jobs[job.id] = job
        for old in list(self.jobs)[:-30]:
            self.jobs.pop(old, None)
        self._pool.submit(self._run, job, model)
        return job

    def _run(self, job: Job, model: dict[str, Any]) -> None:
        if job.cancel.is_set():
            job.status = "cancelled"
            return
        job.status = "running"
        try:
            for i in range(job.params["count"]):
                if job.cancel.is_set():
                    break
                seed = (job.params["seed"] + i) % (2**31)
                png = self._remote(model, job.params, seed) if model.get("format") == "remote_image" else self._local(job, model, seed, i)
                if png is None:
                    break
                meta = {k: job.params[k] for k in ("prompt", "negative", "steps", "width", "height", "guidance")}
                job.images.append(save_image(png, {**meta, "seed": seed, "model": model["name"]}))
                if model.get("format") == "remote_image":
                    job.step = (i + 1) * job.params["steps"]
            job.status = "cancelled" if job.cancel.is_set() else "done"
        except Exception as exc:  # noqa: BLE001 — причина показывается пользователю
            job.status, job.error = "error", str(exc) or exc.__class__.__name__

    # --- внешний сервер ---
    @staticmethod
    def _remote(model: dict[str, Any], p: dict[str, Any], seed: int) -> bytes:
        base = model["base_url"].rstrip("/")
        with httpx.Client(timeout=httpx.Timeout(600, connect=15)) as c:
            if model.get("api") == "openai":
                body = {"model": model.get("remote_model") or "default", "prompt": p["prompt"], "n": 1, "size": f"{p['width']}x{p['height']}", "response_format": "b64_json"}
                r = c.post(f"{base}/images/generations", json=body)
                r.raise_for_status()
                return base64.b64decode(r.json()["data"][0]["b64_json"])
            root = re.sub(r"/(v1|sdapi/v1)$", "", base)
            body = {"prompt": p["prompt"], "negative_prompt": p["negative"], "steps": p["steps"], "width": p["width"], "height": p["height"], "seed": seed, "cfg_scale": p["guidance"], "batch_size": 1}
            r = c.post(f"{root}/sdapi/v1/txt2img", json=body)
            r.raise_for_status()
            return base64.b64decode(r.json()["images"][0].split(",", 1)[-1])

    # --- локально (diffusers) ---
    def _load(self, model: dict[str, Any]) -> Any:
        if self._loaded == model["id"]:
            return self._pipe
        try:
            import torch
            from diffusers import AutoPipelineForText2Image, StableDiffusionPipeline
        except ImportError as exc:
            raise ImageError("Для локальной генерации: pip install diffusers torch transformers accelerate safetensors — либо подключите внешний сервер (вкладка «Свой сервер»)") from exc
        device = "cuda" if torch.cuda.is_available() else "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu"
        dtype = torch.float16 if device != "cpu" else torch.float32
        path = Path(model["path"])
        if path.is_dir():
            pipe = AutoPipelineForText2Image.from_pretrained(path, torch_dtype=dtype)
        elif path.suffix in (".safetensors", ".ckpt"):
            pipe = StableDiffusionPipeline.from_single_file(path, torch_dtype=dtype)
        else:
            raise ImageError("Нужна diffusers-папка или .safetensors чекпойнт")
        self._pipe, self._loaded = pipe.to(device), model["id"]
        return self._pipe

    def _local(self, job: Job, model: dict[str, Any], seed: int, index: int) -> bytes | None:
        import io

        import torch

        pipe = self._load(model)
        p = job.params
        base = index * p["steps"]

        def on_step(pipeline: Any, step: int, _t: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
            job.step = base + step + 1
            if job.cancel.is_set():
                pipeline._interrupt = True  # noqa: SLF001 — штатный способ остановки diffusers
            return kwargs

        args = dict(prompt=p["prompt"], negative_prompt=p["negative"] or None, num_inference_steps=p["steps"], width=p["width"], height=p["height"], guidance_scale=p["guidance"], generator=torch.Generator().manual_seed(seed))
        try:
            image = pipe(**args, callback_on_step_end=on_step).images[0]
        except TypeError:  # старые версии diffusers без callback_on_step_end
            image = pipe(**args).images[0]
        if job.cancel.is_set():
            return None
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
