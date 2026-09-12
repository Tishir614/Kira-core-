from app.blender.scripts import smoke_script


def test_smoke_script_has_real_render(tmp_path):
    script = smoke_script(str(tmp_path / "smoke.png"))
    assert "bpy.ops.render.render(write_still=True)" in script and "camera" in script
