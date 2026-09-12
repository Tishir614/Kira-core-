from pathlib import Path
from app.blender.runner import run_blender
from app.blender.scripts import project_script


def import_model(source: Path, project_dir: Path) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    output = project_dir / "imported.blend"
    script = project_dir / "import_model.py"
    script.write_text(project_script(str(source), str(output)), encoding="utf-8")
    run_blender(script, project_dir / "import.log")
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("Blender did not create a valid project")
    return output
