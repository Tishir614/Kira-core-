from __future__ import annotations
import json, zipfile
from pathlib import Path

ALLOWED_ROOTS = {
    "input": "source",
    "blender": "model",
    "textures": "textures",
    "audio": "source/audio",
    "render": "renders",
    "exports": "exports",
    "alight": "alight",
}


def build_project_package(project: Path, output: Path, metadata: dict) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    safe_metadata = {k: v for k, v in metadata.items() if not any(secret in k.lower() for secret in ("token", "secret", "key", "password"))}
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for source_name, target_name in ALLOWED_ROOTS.items():
            source = project / source_name
            if source.exists():
                for item in source.rglob("*"):
                    if item.is_file() and not item.is_symlink():
                        archive.write(item, Path("project") / target_name / item.relative_to(source))
        archive.writestr("project/metadata.json", json.dumps(safe_metadata, ensure_ascii=False, indent=2))
        archive.writestr("project/README.txt", "Kira Animator project package. No credentials are included.\n")
    return output
