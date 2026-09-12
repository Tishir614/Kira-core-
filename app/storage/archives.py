from __future__ import annotations
import stat, zipfile
from pathlib import Path


def safe_extract_zip(archive: Path, destination: Path, max_files: int = 1000, max_uncompressed: int = 2 * 1024**3, max_ratio: int = 100) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    extracted = []
    total = 0
    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        if len(infos) > max_files:
            raise ValueError("archive contains too many files")
        for info in infos:
            parts = Path(info.filename).parts
            if Path(info.filename).is_absolute() or ".." in parts:
                raise ValueError("archive path traversal")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("archive symlinks are forbidden")
            total += info.file_size
            if total > max_uncompressed:
                raise ValueError("archive expands beyond quota")
            if info.compress_size and info.file_size / info.compress_size > max_ratio:
                raise ValueError("suspicious compression ratio")
        for info in infos:
            target = (destination / info.filename).resolve()
            if destination.resolve() not in target.parents and target != destination.resolve():
                raise ValueError("archive path escapes destination")
            zf.extract(info, destination)
            extracted.append(target)
    return extracted
