from __future__ import annotations
import uuid
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import File, Project, User
from app.storage.files import project_dirs, safe_name, save_upload_hashed, validate_file


class ProjectNotFound(LookupError):
    pass


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def user(self, telegram_id: int) -> User:
        user = (await self.db.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
        if not user:
            user = User(telegram_id=telegram_id)
            self.db.add(user)
            await self.db.flush()
        return user

    async def create(self, telegram_id: int, name: str, prompt: str = "") -> Project:
        user = await self.user(telegram_id)
        project = Project(user_id=user.id, name=name, prompt=prompt)
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        project_dirs(telegram_id, str(project.id))
        return project

    async def owned(self, project_id: uuid.UUID, telegram_id: int) -> Project:
        project = (await self.db.execute(select(Project).join(User).where(Project.id == project_id, User.telegram_id == telegram_id))).scalar_one_or_none()
        if not project:
            raise ProjectNotFound("Проект не найден")
        return project

    async def add_upload(self, project_id: uuid.UUID, telegram_id: int, upload: UploadFile, category: str) -> File:
        await self.owned(project_id, telegram_id)
        name = safe_name(upload.filename or "upload")
        validate_file(name, upload.content_type or "application/octet-stream", upload.size)
        destination = project_dirs(telegram_id, str(project_id))["input"] / f"{uuid.uuid4().hex}_{name}"
        size, digest = await save_upload_hashed(upload, destination)
        duplicate = (await self.db.execute(select(File).where(File.project_id == project_id, File.sha256 == digest))).scalar_one_or_none()
        if duplicate:
            destination.unlink(missing_ok=True)
            return duplicate
        record = File(
            project_id=project_id,
            name=name,
            mime_type=upload.content_type or "application/octet-stream",
            category=category,
            path=str(destination),
            sha256=digest,
            size=size,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def inputs(self, project_id: uuid.UUID, telegram_id: int, category: str | None = None) -> list[File]:
        await self.owned(project_id, telegram_id)
        query = select(File).where(File.project_id == project_id)
        if category:
            query = query.where(File.category == category)
        return list((await self.db.execute(query)).scalars())
