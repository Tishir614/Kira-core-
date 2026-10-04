import enum, uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Status(str, enum.Enum):
    created = "created"
    queued = "queued"
    running = "running"
    awaiting_review = "awaiting_review"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"
    failed = "failed"
    completed = "completed"


class GateResult(str, enum.Enum):
    PASS = "PASS"  # nosec B105 - статус проверки, не пароль
    WARNING = "WARNING"
    FAIL = "FAIL"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.created)
    prompt: Mapped[str] = mapped_column(Text, default="")
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    files: Mapped[list["File"]] = relationship(cascade="all, delete-orphan")


class File(Base):
    __tablename__ = "files"
    __table_args__ = (UniqueConstraint("project_id", "sha256"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(30))
    path: Mapped[str] = mapped_column(Text)
    object_key: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    celery_id: Mapped[str | None] = mapped_column(String(100), index=True)
    type: Mapped[str] = mapped_column(String(50))
    queue: Mapped[str] = mapped_column(String(30), default="cpu")
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.created)
    progress_stage: Mapped[str] = mapped_column(String(100), default="created")
    stage_index: Mapped[int] = mapped_column(Integer, default=0)
    stage_count: Mapped[int] = mapped_column(Integer, default=0)
    requires_gpu: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_memory_mb: Mapped[int] = mapped_column(Integer, default=1024)
    estimated_vram_mb: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    max_execution_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    max_disk_mb: Mapped[int] = mapped_column(Integer, default=10240)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_gpu_time: Mapped[float | None] = mapped_column(Float)
    provider_cost: Mapped[float | None] = mapped_column(Float)
    render_time: Mapped[float | None] = mapped_column(Float)


class ProjectVersion(Base):
    __tablename__ = "project_versions"
    __table_args__ = (UniqueConstraint("project_id", "number"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project_versions.id"))
    object_prefix: Mapped[str] = mapped_column(Text)
    identity_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    generation_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    __table_args__ = (UniqueConstraint("project_id", "version_id", "stage_index"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_versions.id"))
    stage_index: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(100))
    object_key: Mapped[str] = mapped_column(Text)
    gate: Mapped[GateResult] = mapped_column(Enum(GateResult))
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectInstruction(Base):
    __tablename__ = "project_instructions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProjectContext(Base):
    __tablename__ = "project_contexts"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    character_description: Mapped[str] = mapped_column(Text, default="")
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    model_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    rig_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    animation_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    previous_changes: Mapped[list] = mapped_column(JSON, default=list)
    user_preferences: Mapped[dict] = mapped_column(JSON, default=dict)


class QualityGate(Base):
    __tablename__ = "quality_gates"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    stage: Mapped[str] = mapped_column(String(100))
    result: Mapped[GateResult] = mapped_column(Enum(GateResult))
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Render(Base):
    __tablename__ = "renders"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.created)


class BlenderJob(Base):
    __tablename__ = "blender_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    script_path: Mapped[str] = mapped_column(Text)
    log_path: Mapped[str] = mapped_column(Text)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.created)


class AlightProject(Base):
    __tablename__ = "alight_projects"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    package_path: Mapped[str] = mapped_column(Text)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.created)
