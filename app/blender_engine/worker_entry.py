"""Fixed Blender entrypoint. Usage after `--`: plan.json project_root."""

import json, logging, sys
from pathlib import Path
from pydantic import ValidationError
from app.blender_engine.executor import BlenderPlanExecutor
from app.blender_engine.models import BlenderPlan

args = sys.argv[sys.argv.index("--") + 1 :]
if len(args) != 2:
    raise SystemExit("Expected plan path and project root")
plan_path = Path(args[0]).resolve()
root = Path(args[1]).resolve()
if root not in plan_path.parents:
    raise SystemExit("Plan must be inside project root")
plan = BlenderPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
BlenderPlanExecutor(root, logging.getLogger("kira.blender")).execute(plan)
