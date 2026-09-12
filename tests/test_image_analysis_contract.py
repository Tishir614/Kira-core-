from pathlib import Path


def test_provider_requires_segmentation_and_depth():
    source = Path("app/image_to_3d/providers/base.py").read_text()
    assert "async def segment" in source and "async def estimate_depth" in source


def test_all_semantic_masks_are_declared():
    source = Path("app/image_to_3d/providers/http.py").read_text()
    for label in ("background", "head", "hair_fur", "hands_paws", "tail", "accessories"):
        assert label in source
