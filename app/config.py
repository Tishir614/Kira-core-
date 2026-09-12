from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


@dataclass
class Settings:
    telegram_bot_token: str
    database_url: str
    redis_url: str
    openai_api_key: str
    projects_root: Path
    max_upload_mb: int
    blender_bin: str
    ffmpeg_bin: str
    external_storage_url: str
    image_to_3d_provider_url: str
    image_to_3d_provider_key: str
    backend_url: str
    admin_token: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        database_url=os.getenv("DATABASE_URL", "postgresql+asyncpg://kira:kira@postgres:5432/kira"),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        projects_root=Path(os.getenv("PROJECTS_ROOT", "projects")),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "100")),
        blender_bin=os.getenv("BLENDER_BIN", "blender"),
        ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
        external_storage_url=os.getenv("EXTERNAL_STORAGE_URL", ""),
        image_to_3d_provider_url=os.getenv("IMAGE_TO_3D_PROVIDER_URL", ""),
        image_to_3d_provider_key=os.getenv("IMAGE_TO_3D_PROVIDER_KEY", ""),
        backend_url=os.getenv("BACKEND_URL", "http://api:8000"),
        admin_token=os.getenv("ADMIN_TOKEN", ""),
    )
