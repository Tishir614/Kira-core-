from __future__ import annotations
from dataclasses import dataclass
from app.ai.planner import plan_pipeline
from app.workers.tasks import image_to_3d_task


@dataclass(frozen=True)
class EnqueuedJob:
    task_id: str
    stages: list[str]


class TaskOrchestrator:
    def enqueue_image_to_3d(self, project_id: str, user_id: int, paths: list[str], prompt: str, quality: str) -> EnqueuedJob:
        stages = [s.key for s in plan_pipeline([*paths], prompt)]
        result = image_to_3d_task.apply_async(
            args=[project_id, user_id, paths, prompt, quality], queue="gpu", priority=5, time_limit=7200, soft_time_limit=7000
        )
        return EnqueuedJob(result.id, stages)
