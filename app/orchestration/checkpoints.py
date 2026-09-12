from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

STAGES = ("01_input", "02_preprocessed", "03_multiview", "04_base_mesh", "05_clean_mesh", "06_retopology", "07_textures", "08_rig", "09_animation", "10_render")


@dataclass(frozen=True)
class ResumePoint:
    index: int
    stage: str
    artifact: Path


class CheckpointStore:
    def __init__(self, project: Path, version: int):
        self.root = project / "versions" / f"{version:04d}"

    def save(self, stage: str, source: Path, name: str) -> Path:
        if stage not in STAGES:
            raise ValueError("unknown checkpoint stage")
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError("checkpoint artifact is invalid")
        import shutil

        target = self.root / stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".partial")
        shutil.copy2(source, temporary)
        temporary.replace(target)
        return target

    def latest(self) -> ResumePoint | None:
        for index in range(len(STAGES) - 1, -1, -1):
            directory = self.root / STAGES[index]
            files = (
                sorted((p for p in directory.glob("*") if p.is_file() and not p.name.endswith(".partial")), key=lambda p: p.stat().st_mtime, reverse=True)
                if directory.exists()
                else []
            )
            if files:
                return ResumePoint(index, STAGES[index], files[0])
        return None
