"""Генерация изображений локальной моделью через diffusers (необязательная зависимость)."""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from .config import outputs_dir


class ImageError(Exception):
    pass


def available() -> bool:
    try:
        import diffusers  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


class ImageGenerator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pipe: Any = None
        self._loaded: str | None = None

    def _load(self, model: dict[str, Any]) -> Any:
        if self._loaded == model["id"]:
            return self._pipe
        try:
            import torch
            from diffusers import AutoPipelineForText2Image, StableDiffusionPipeline
        except ImportError as exc:
            raise ImageError("Для генерации изображений: pip install diffusers torch transformers accelerate safetensors") from exc
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

    def generate(self, model: dict[str, Any], prompt: str, negative: str, steps: int, width: int, height: int, seed: int | None) -> str:
        import torch

        with self._lock:
            pipe = self._load(model)
            gen = torch.Generator().manual_seed(seed) if seed is not None else None
            image = pipe(prompt=prompt, negative_prompt=negative or None, num_inference_steps=steps, width=width, height=height, generator=gen).images[0]
        name = f"{uuid.uuid4().hex[:12]}.png"
        image.save(outputs_dir() / name)
        return name
