import zipfile
import pytest
from app.storage.archives import safe_extract_zip
from app.orchestration.checkpoints import CheckpointStore


def test_zip_slip_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../escape", "bad")
    with pytest.raises(ValueError):
        safe_extract_zip(archive, tmp_path / "out")


def test_checkpoint_resume(tmp_path):
    source = tmp_path / "model.blend"
    source.write_bytes(b"blend")
    store = CheckpointStore(tmp_path / "project", 2)
    saved = store.save("05_clean_mesh", source, "model.blend")
    assert store.latest().artifact == saved
