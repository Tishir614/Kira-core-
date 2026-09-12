import pytest
from app.image_to_3d.providers.base import Analysis, Quality, ReconstructionRequest
from app.image_to_3d.providers.http import HTTPImageTo3DProvider


def test_provider_rejects_non_http():
    with pytest.raises(ValueError):
        HTTPImageTo3DProvider("file:///tmp/provider")


def test_request_tracks_quality_and_uncertainty(tmp_path):
    a = Analysis("anthro", ["tail"], {}, ["#ffffff"], ["fur"], ["front"], ["back inferred"])
    r = ReconstructionRequest([tmp_path / "front.png"], "anthro", Quality.HIGH, tmp_path, a)
    assert r.analysis.uncertainty == ["back inferred"] and r.quality is Quality.HIGH
