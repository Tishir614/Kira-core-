import json, logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": record.levelname,
                "message": record.getMessage(),
                "user_id": getattr(record, "user_id", None),
                "project_id": getattr(record, "project_id", None),
                "task_id": getattr(record, "task_id", None),
                "worker": getattr(record, "worker", None),
                "stage": getattr(record, "stage", None),
            },
            ensure_ascii=False,
        )


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
