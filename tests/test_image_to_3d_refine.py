from app.image_to_3d.blender_refine import refinement_script


def test_refinement_is_volumetric_and_exports(tmp_path):
    s = refinement_script(tmp_path / "mesh.glb", tmp_path / "out")
    assert "calc_volume" in s and "plane/billboard" in s
    assert "smart_project" in s and "export_scene.gltf" in s
    assert all(view in s for view in ("front", "side", "back", "three_quarter"))


def test_blender_disables_autoexec():
    from pathlib import Path
    from unittest.mock import patch
    from app.blender.runner import run_blender

    with patch("app.blender.runner.subprocess.run") as run:
        run.return_value.returncode = 0
        run_blender(Path("x.py"), Path("/tmp/kira-test.log"))
        assert "--disable-autoexec" in run.call_args.args[0]
