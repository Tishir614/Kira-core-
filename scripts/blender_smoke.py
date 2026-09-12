from pathlib import Path
from app.blender.runner import run_blender
from app.blender.scripts import smoke_script

root = Path("renders/smoke")
root.mkdir(parents=True, exist_ok=True)
script = root / "smoke.py"
output = root / "smoke.png"
script.write_text(smoke_script(str(output)), encoding="utf-8")
run_blender(script, root / "blender.log", 300)
if not output.is_file() or output.stat().st_size == 0:
    raise SystemExit("Smoke render missing")
print(output)
