from pathlib import Path


def test_revision_modifies_existing_mesh():
    source = Path("app/image_to_3d/providers/http.py").read_text()
    assert "/v1/revise" in source and "modify_existing_mesh" in source
