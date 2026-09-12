import pytest
from app.video.engine import VideoSpec


def test_video_specs():
    VideoSpec(1080, 1920, 60).validate()


def test_bad_fps():
    with pytest.raises(ValueError):
        VideoSpec(fps=25).validate()
