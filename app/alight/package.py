import json, shutil, zipfile
from pathlib import Path

REQUIRED = ("background.png", "character.png", "overlay.png", "effects.mp4", "audio.mp3")


def build_asset_pack(destination: Path, assets: dict[str, Path], markers: list[dict], keyframes: list[dict]) -> Path:
    """Builds a documented asset pack; it does not claim to be a proprietary Alight Motion project."""
    work = destination.with_suffix("")
    work.mkdir(parents=True, exist_ok=True)
    for name, source in assets.items():
        if name not in REQUIRED:
            raise ValueError(f"Unexpected asset name: {name}")
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, work / name)
    (work / "timing.json").write_text(json.dumps(markers, ensure_ascii=False, indent=2), encoding="utf-8")
    (work / "keyframes.json").write_text(json.dumps(keyframes, ensure_ascii=False, indent=2), encoding="utf-8")
    (work / "README.txt").write_text(
        "Kira Animator Asset Pack\nИмпортируйте assets вручную и примените keyframes.json. Официальный API Alight Motion не используется.\n", encoding="utf-8"
    )
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(work.iterdir()):
            archive.write(path, path.name)
    return destination
