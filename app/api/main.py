import uuid
from fastapi import Depends, FastAPI, File as UploadField, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_session
from app.image_to_3d.providers.base import Quality
from app.orchestration.service import TaskOrchestrator
from app.services.projects import ProjectNotFound, ProjectService

app = FastAPI(title="Kira Animator API", version="0.2.0")


class ProjectIn(BaseModel):
    name: str = "Новый проект"
    prompt: str = ""


class ReconstructionIn(BaseModel):
    prompt: str
    quality: Quality


async def user_id(x_telegram_user_id: int = Header(alias="X-Telegram-User-Id")) -> int:
    if x_telegram_user_id <= 0:
        raise HTTPException(401, "Invalid Telegram identity")
    return x_telegram_user_id


@app.exception_handler(ProjectNotFound)
async def not_found(_, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}


@app.post("/projects", status_code=201)
async def create_project(body: ProjectIn, uid: int = Depends(user_id), db: AsyncSession = Depends(get_session)):
    project = await ProjectService(db).create(uid, body.name, body.prompt)
    return {"id": str(project.id), "status": project.status}


@app.get("/projects/{project_id}")
async def get_project(project_id: uuid.UUID, uid: int = Depends(user_id), db: AsyncSession = Depends(get_session)):
    p = await ProjectService(db).owned(project_id, uid)
    return {"id": str(p.id), "name": p.name, "prompt": p.prompt, "status": p.status}


@app.post("/projects/{project_id}/uploads", status_code=201)
async def upload(
    project_id: uuid.UUID,
    upload: UploadFile = UploadField(...),
    category: str = Form("input"),
    uid: int = Depends(user_id),
    db: AsyncSession = Depends(get_session),
):
    record = await ProjectService(db).add_upload(project_id, uid, upload, category)
    return {"id": str(record.id), "name": record.name, "size": record.size}


@app.post("/projects/{project_id}/image-to-3d", status_code=202)
async def reconstruct(project_id: uuid.UUID, body: ReconstructionIn, uid: int = Depends(user_id), db: AsyncSession = Depends(get_session)):
    service = ProjectService(db)
    project = await service.owned(project_id, uid)
    files = await service.inputs(project.id, uid, "reference")
    if not files:
        raise HTTPException(409, "Reference images are required")
    from app.ai.planner import plan_pipeline
    from app.database.models import Status, Task

    stages = [stage.key for stage in plan_pipeline([file.path for file in files], body.prompt)]
    task = Task(
        project_id=project.id,
        type="image_to_3d",
        queue="gpu",
        status=Status.queued,
        progress_stage="queued",
        stage_count=len(stages),
        requires_gpu=True,
        estimated_memory_mb=8192,
        estimated_vram_mb=8192,
        max_execution_seconds=7200,
    )
    db.add(task)
    await db.flush()
    try:
        job = TaskOrchestrator().enqueue_image_to_3d(str(project.id), uid, [file.path for file in files], body.prompt, body.quality.value)
    except Exception as exc:
        task.status = Status.failed
        task.error = f"Queue unavailable: {exc}"[:2000]
        await db.commit()
        raise HTTPException(503, "Task queue is unavailable") from exc
    task.celery_id = job.task_id
    await db.commit()
    return {"task_id": str(task.id), "celery_id": job.task_id, "stages": job.stages, "status": "queued"}


@app.get("/projects/{project_id}/files")
async def files(project_id: uuid.UUID, uid: int = Depends(user_id), db: AsyncSession = Depends(get_session)):
    rows = await ProjectService(db).inputs(project_id, uid)
    return [{"id": str(f.id), "name": f.name, "mime_type": f.mime_type, "size": f.size} for f in rows]


@app.get("/projects/{project_id}/status")
async def project_status(project_id: uuid.UUID, uid: int = Depends(user_id), db: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from app.database.models import Task

    project = await ProjectService(db).owned(project_id, uid)
    tasks = list((await db.execute(select(Task).where(Task.project_id == project.id).order_by(Task.created_at.desc()))).scalars())
    return {
        "project": project.name,
        "status": project.status,
        "tasks": [
            {
                "id": str(t.id),
                "stage": t.progress_stage,
                "stage_index": t.stage_index,
                "stage_count": t.stage_count,
                "status": t.status,
                "queue": t.queue,
                "error": t.error,
            }
            for t in tasks
        ],
    }


@app.post("/projects/{project_id}/tasks/{task_id}/cancel", status_code=202)
async def cancel_task(project_id: uuid.UUID, task_id: uuid.UUID, uid: int = Depends(user_id), db: AsyncSession = Depends(get_session)):
    from app.database.models import Status, Task

    await ProjectService(db).owned(project_id, uid)
    task = await db.get(Task, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(404, "Task not found")
    if task.status not in {Status.queued, Status.running}:
        raise HTTPException(409, "Task is not cancellable")
    task.status = Status.cancel_requested
    await db.commit()
    if task.celery_id:
        from app.workers.celery_app import celery_app

        celery_app.control.revoke(task.celery_id, terminate=False)
    return {"status": "cancel_requested", "checkpoint_policy": "save_current_stage"}


@app.get("/tasks")
async def user_tasks(uid: int = Depends(user_id), db: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from app.database.models import Project, Task, User

    rows = (
        await db.execute(select(Task, Project.name).join(Project).join(User).where(User.telegram_id == uid).order_by(Task.created_at.desc()).limit(100))
    ).all()
    return [
        {
            "id": str(task.id),
            "project": name,
            "stage": task.progress_stage,
            "stage_index": task.stage_index,
            "stage_count": task.stage_count,
            "status": task.status,
            "queue": task.queue,
        }
        for task, name in rows
    ]


@app.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_session)):
    from sqlalchemy import func, select
    from app.database.models import Status, Task
    from fastapi.responses import PlainTextResponse

    rows = (await db.execute(select(Task.status, func.count(Task.id)).group_by(Task.status))).all()
    counts = {status.value: count for status, count in rows}
    body = "\n".join([f'kira_tasks{{status="{status}"}} {counts.get(status,0)}' for status in ("queued", "running", "failed", "completed")]) + "\n"
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")


@app.get("/admin")
async def admin(x_admin_token: str = Header(default="", alias="X-Admin-Token"), db: AsyncSession = Depends(get_session)):
    from sqlalchemy import func, select
    from app.config import get_settings
    from app.database.models import Project, Task, User
    from fastapi.responses import HTMLResponse

    if not get_settings().admin_token or x_admin_token != get_settings().admin_token:
        raise HTTPException(403, "Forbidden")
    users = await db.scalar(select(func.count(User.id)))
    projects = await db.scalar(select(func.count(Project.id)))
    tasks = (await db.execute(select(Task).order_by(Task.created_at.desc()).limit(50))).scalars()
    rows = "".join(f"<tr><td>{t.id}</td><td>{t.queue}</td><td>{t.progress_stage}</td><td>{t.status.value}</td></tr>" for t in tasks)
    return HTMLResponse(
        f"<h1>Kira Admin</h1><p>Users: {users} Projects: {projects}</p><table><tr><th>Task</th><th>Queue</th><th>Stage</th><th>Status</th></tr>{rows}</table>"
    )
