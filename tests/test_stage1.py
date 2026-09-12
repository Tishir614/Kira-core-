from pathlib import Path
import pytest
from app.storage.files import safe_name, validate_file
from app.config import get_settings


def test_safe_name_blocks_traversal():
    assert safe_name("../../secret cat.png") == "secret_cat.png"


def test_valid_upload():
    validate_file("hero.glb", "model/gltf-binary", 100)


def test_invalid_extension():
    with pytest.raises(ValueError):
        validate_file("attack.py", "text/x-python", 10)


def test_project_isolation(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "projects_root", tmp_path)
    from app.storage.files import project_dirs

    assert project_dirs(1, "a")["input"] != project_dirs(2, "a")["input"]
