from pathlib import Path


def test_api_dockerfile_does_not_pin_expired_debian_revisions():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "ffmpeg=" not in dockerfile
    assert "libmagic1=" not in dockerfile
    assert "--no-install-recommends ffmpeg libmagic1" in dockerfile


def test_blender_worker_uses_python_dependency_lock():
    dockerfile = Path("docker/Dockerfile.blender").read_text(encoding="utf-8")
    assert "COPY requirements.lock" in dockerfile
    assert "-r requirements.lock" in dockerfile
    assert "pip3 install --break-system-packages celery" not in dockerfile
