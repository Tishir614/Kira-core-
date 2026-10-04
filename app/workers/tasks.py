import asyncio, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def dispatch_pipeline(self, project_id: str, stages: list[str]) -> dict:
    return {"project_id": project_id, "stages": stages, "task_id": self.request.id}


async def _set_status(project_id: str, status: str, stage: str, error: str | None = None, task_id: str | None = None) -> None:
    from sqlalchemy import select
    from app.database.models import Project, Status, Task
    from app.database.session import SessionLocal

    async with SessionLocal() as db:
        project = await db.get(Project, uuid.UUID(project_id))
        if project:
            project.status = Status(status)
        task = (
            (await db.execute(select(Task).where(Task.project_id == uuid.UUID(project_id), Task.type == "image_to_3d").order_by(Task.created_at.desc())))
            .scalars()
            .first()
        )
        if not task:
            task = Task(project_id=uuid.UUID(project_id), type="image_to_3d")
            db.add(task)
        task.status = Status(status)
        task.progress_stage = stage
        ordered_stages = (
            "queued",
            "image_analysis",
            "segmentation",
            "depth_estimation",
            "multiview",
            "mesh_reconstruction",
            "texture_generation",
            "blender_refinement",
            "preview_review",
        )
        if stage in ordered_stages:
            task.stage_index = ordered_stages.index(stage) + 1
            task.stage_count = len(ordered_stages)
        task.error = error
        if status in {"failed", "completed", "awaiting_review"}:
            task.finished_at = datetime.now(timezone.utc)
        await db.commit()


async def _run_image_to_3d(project_id: str, user_id: int, image_paths: list[str], prompt: str, quality: str) -> dict:
    from aiogram import Bot
    from aiogram.types import FSInputFile, InputMediaPhoto
    from app.bot.keyboards import review_menu
    from app.config import get_settings
    from app.image_to_3d.pipeline import ImageTo3DPipeline
    from app.image_to_3d.providers import HTTPImageTo3DProvider
    from app.image_to_3d.providers.base import Quality

    settings = get_settings()
    if not settings.image_to_3d_provider_url:
        raise RuntimeError("Image-to-3D provider is not configured; reconstruction was not started")
    root = settings.projects_root / str(user_id) / project_id
    await _set_status(project_id, "running", "image_analysis")
    provider = HTTPImageTo3DProvider(settings.image_to_3d_provider_url, settings.image_to_3d_provider_key)

    async def progress(stage: str):
        await _set_status(project_id, "running", stage)

    artifacts = await ImageTo3DPipeline(provider, progress).run([Path(x) for x in image_paths], prompt, Quality(quality), root, rig_required=False)
    await _set_status(project_id, "awaiting_review", "preview_review")
    bot = Bot(settings.telegram_bot_token)
    try:
        media: list[Any] = [
            InputMediaPhoto(media=FSInputFile(path), caption="Скрытые стороны восстановлены приблизительно." if len(image_paths) == 1 and i == 0 else None)
            for i, path in enumerate(artifacts.previews)
        ]
        await bot.send_media_group(user_id, media)
        await bot.send_message(user_id, "Проверьте Front / Side / Back / 3/4. Экспорт ещё не подтверждён.", reply_markup=review_menu())
    finally:
        await bot.session.close()
    return {"blend": str(artifacts.blend), "glb": str(artifacts.glb), "previews": [str(x) for x in artifacts.previews]}


@celery_app.task(bind=True, acks_late=True)
def image_to_3d_task(self, project_id: str, user_id: int, image_paths: list[str], prompt: str, quality: str) -> dict:
    try:
        return asyncio.run(_run_image_to_3d(project_id, user_id, image_paths, prompt, quality))
    except Exception as exc:
        asyncio.run(_set_status(project_id, "failed", "stopped", str(exc)[:2000]))
        settings = __import__("app.config", fromlist=["get_settings"]).get_settings()
        if settings.telegram_bot_token:
            error_message = str(exc)[:500]

            async def notify():
                from aiogram import Bot

                bot = Bot(settings.telegram_bot_token)
                try:
                    await bot.send_message(
                        user_id, f"Не удалось создать безопасную 3D-модель: {error_message}. Проект сохранён; повреждённый файл не отправлен."
                    )
                finally:
                    await bot.session.close()

            asyncio.run(notify())
        raise


async def _run_revision(project_id: str, user_id: int, feedback: str, area: str) -> dict:
    from aiogram import Bot
    from aiogram.types import FSInputFile, InputMediaPhoto
    from app.bot.keyboards import review_menu
    from app.config import get_settings
    from app.image_to_3d.pipeline import ImageTo3DPipeline
    from app.image_to_3d.providers import HTTPImageTo3DProvider

    settings = get_settings()
    root = settings.projects_root / str(user_id) / project_id
    candidates = sorted(root.glob("revisions/*/blender/Character.blend"), key=lambda p: p.stat().st_mtime, reverse=True)
    current = candidates[0] if candidates else root / "blender" / "Character.blend"
    revision = root / "revisions" / str(uuid.uuid4())
    provider = HTTPImageTo3DProvider(settings.image_to_3d_provider_url, settings.image_to_3d_provider_key)

    async def progress(stage: str):
        await _set_status(project_id, "running", stage)

    result = await ImageTo3DPipeline(provider, progress).revise(current, feedback, area, revision)
    await _set_status(project_id, "awaiting_review", "revision_review")
    bot = Bot(settings.telegram_bot_token)
    try:
        await bot.send_media_group(user_id, [InputMediaPhoto(media=FSInputFile(x)) for x in result.previews])
        await bot.send_message(user_id, "Исправлена текущая модель. Проверьте новые ракурсы.", reply_markup=review_menu())
    finally:
        await bot.session.close()
    return {"blend": str(result.blend), "glb": str(result.glb)}


@celery_app.task(bind=True, acks_late=True)
def image_to_3d_revision_task(self, project_id: str, user_id: int, feedback: str, area: str) -> dict:
    try:
        return asyncio.run(_run_revision(project_id, user_id, feedback, area))
    except Exception as exc:
        asyncio.run(_set_status(project_id, "failed", "revision_stopped", str(exc)[:2000]))
        raise
