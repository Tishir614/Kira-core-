import subprocess
from pathlib import Path
from app.config import get_settings


def run_blender(script: Path, log: Path, timeout: int = 3600) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as stream:
        result = subprocess.run(
            [get_settings().blender_bin, "--background", "--disable-autoexec", "--python", str(script.resolve())],
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    if result.returncode:
        raise RuntimeError(f"Blender завершился с кодом {result.returncode}; см. {log}")
