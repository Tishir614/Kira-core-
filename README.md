# Kira Animator Bot

Kira is a staged Telegram animation backend: **Telegram → FastAPI → ProjectService → planner/orchestrator → CPU/GPU/Blender/render/video queues → quality gates → S3-compatible storage → Telegram**. Telegram handlers only stream inputs to the backend and enqueue jobs; they never run AI, Blender, or FFmpeg.

## What is implemented

- Multi-reference Art/Image → 3D flow with persistent FSM state, Draft/Good/High presets, explicit single-view uncertainty, four-view review, immutable revisions, and fail-closed provider errors.
- Replaceable provider contracts for analysis, masks, depth, multiview, volumetric mesh, PBR textures, and identity-preserving targeted revision. Configure a real service; Kira never uses a plane/billboard as “3D”.
- A strictly typed Pydantic `BlenderPlan`. Unknown fields/operations, traversal paths, arbitrary code, shell/network operations, `exec`, and `eval` are rejected. A fixed worker entrypoint translates whitelisted data into controlled `bpy` calls.
- Blender cleanup and gates for readable mesh, volume/thickness, UV, materials, normals, preview renders, and exports; embedded BLEND scripts are disabled. Rig checks require bones, modifiers, weights, and changed transforms in test poses.
- SHA-256 streaming ingestion/deduplication, hardened ZIP extraction, S3-compatible adapter, atomic stage checkpoints, project versions/context/instruction history, and sanitized whole-project packages.
- Beat analysis, lip-sync visemes with envelope fallback, skeleton retarget mapping, FFmpeg encoding/ffprobe validation, and honest Alight Motion timeline/asset packs.

## Provider contract

Set `IMAGE_TO_3D_PROVIDER_URL` and optional `IMAGE_TO_3D_PROVIDER_KEY`. The compatible service exposes `POST /v1/analyze`, `/v1/segment`, `/v1/depth`, `/v1/multiview`, `/v1/mesh`, `/v1/textures`, and `/v1/revise`, returning artifact URLs on the configured origin. Requests include every reference, quality, identity lock, prompt, reproducibility settings, and `require_volumetric_mesh=true`. With one image, hidden geometry is marked as approximate. With no provider, the job fails clearly and sends no output.

## Install and run

1. Create a bot with **@BotFather** (`/newbot`). Copy `.env.example` to `.env`; set the bot token, database/Redis URLs, provider, admin token, and S3/MinIO credentials.
2. Install Docker/Compose and run `docker compose up --build`. Alembic migrations run before API startup. API docs: `http://localhost:8000/docs`; probes: `/health`, `/ready`; Prometheus text: `/metrics`; protected admin: `/admin` with `X-Admin-Token`.
3. Local development requires Python 3.12.7, Blender 4.2.3, FFmpeg 5.1.7, PostgreSQL 16.4, and Redis 7.4.0. Run `pip install -r requirements-dev.lock`, `alembic upgrade head`, `uvicorn app.api.main:app`, `python -m app.bot.main`, and the workers shown in Compose.

Telegram calls the backend using `X-Telegram-User-Id`; every project query joins ownership and returns 404 for another user's UUID. Public deployments should replace this internal trust header with signed bot-to-backend authentication at the ingress.

## Recovery, versions, and quality

Stages use `01_input` through `10_render`. Checkpoints are written atomically, and retry code can select the latest completed artifact rather than restart. Every edit creates a version with parent, identity profile, generation metadata (provider/model/seed/settings/prompts/timestamp), and separate object prefix. Quality gates are PASS/WARNING/FAIL; FAIL prevents the next stage. “✅ Готово” is valid only after required artifacts exist, decode/open checks pass, geometry/UV/material checks pass, requested rig/animation checks pass, and final render passes ffprobe.

## Security and operations

User Python is never accepted. BLEND runs use `--disable-autoexec`; subprocesses use argument arrays, project-relative paths, timeouts, non-root containers, queue concurrency and memory limits. ZIP traversal, symlinks, file-count, expanded-size, and compression-ratio bombs are rejected. Apply network policies, GPU runtime limits, malware scanning, object lifecycle/backup policies, Postgres backups, and signed internal authentication in production. Final exports/checkpoints are retained; disposable frames may be lifecycle-expired.

## Validation

- `pytest -q`
- `python -m compileall -q app migrations scripts`
- `python scripts/blender_smoke.py` creates a real cube, camera, light, PNG, and exercises Blender CLI.
- CI runs Ruff, mypy, pytest, Bandit, pip-audit, and a Docker build. No generated binaries belong in Git.

Alight Motion has no claimed private API integration. Kira emits assets, `timeline.json`, typed keyframes, and an animation plan. A future supported importer must be a separate provider.
