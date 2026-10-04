from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    path = Path(os.environ.get("KIRA_LOCAL_DIR", Path.home() / ".kira-local"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def outputs_dir() -> Path:
    path = data_dir() / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path
