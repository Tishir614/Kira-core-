from pathlib import Path


def test_ci_black_matches_repository_formatter():
    requirements = Path("requirements-dev.lock").read_text(encoding="utf-8")
    assert "black==26.3.1" in requirements
