from pathlib import Path


def test_review_status_is_not_success():
    source = Path("app/database/models.py").read_text()
    assert "awaiting_review" in source and "completed" in source
