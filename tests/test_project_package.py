import zipfile
from app.storage.project_package import build_project_package


def test_package_excludes_secrets(tmp_path):
    project = tmp_path / "p"
    (project / "exports").mkdir(parents=True)
    (project / "exports" / "x.glb").write_bytes(b"x")
    output = build_project_package(project, tmp_path / "all.zip", {"seed": 42, "api_key": "secret"})
    with zipfile.ZipFile(output) as z:
        assert "secret" not in z.read("project/metadata.json").decode() and "project/exports/x.glb" in z.namelist()
