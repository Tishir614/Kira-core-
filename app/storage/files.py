from __future__ import annotations
import re
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import UploadFile
from app.config import get_settings

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".mp3", ".wav", ".ogg", ".glb", ".gltf", ".fbx", ".obj", ".blend", ".zip"}
MIME_PREFIXES = ("image/", "video/", "audio/")
MODEL_MIMES = {"model/gltf-binary", "model/gltf+json", "application/octet-stream", "application/zip", "application/x-zip-compressed"}


def safe_name(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:255]


def validate_file(name: str, mime: str, size: int | None = None) -> None:
    settings = get_settings()
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Неподдерживаемый тип файла: {ext}")
    if not (mime.startswith(MIME_PREFIXES) or mime in MODEL_MIMES):
        raise ValueError("MIME type не разрешён")
    if size is not None and size > settings.max_upload_mb * 1024 * 1024:
        raise ValueError("Файл превышает допустимый размер")


def project_dirs(user_id: int, project_id: str) -> dict[str, Path]:
    root = get_settings().projects_root / str(user_id) / str(project_id)
    result = {n: root / n for n in ("input", "blender", "textures", "audio", "render", "exports", "logs")}
    for path in result.values():
        path.mkdir(parents=True, exist_ok=True)
    return result


async def save_upload_hashed(upload: "UploadFile" | Any, destination: Path) -> tuple[int, str]:
    import aiofiles

    limit = get_settings().max_upload_mb * 1024 * 1024
    total = 0
    digest = hashlib.sha256()
    async with aiofiles.open(destination, "wb") as out:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                await out.close()
                destination.unlink(missing_ok=True)
                raise ValueError("Файл превышает допустимый размер")
            digest.update(chunk)
            await out.write(chunk)
    return total, digest.hexdigest()


async def save_upload(upload: "UploadFile" | Any, destination: Path) -> int:
    size, _ = await save_upload_hashed(upload, destination)
    return size
