from celery import Celery
from app.config import get_settings

s = get_settings()
celery_app = Celery("kira", broker=s.redis_url, backend=s.redis_url, include=["app.workers.tasks"])
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_routes={"app.workers.tasks.image_to_3d_task": {"queue": "blender"}, "app.workers.tasks.image_to_3d_revision_task": {"queue": "blender"}},
)
