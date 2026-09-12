from app.blender.rigging import RigOptions, rig_script, animation_script


def test_furry_rig_contains_controls():
    s = rig_script(RigOptions())
    assert all(x in s for x in ["ear.L", "tail.02", "ARMATURE_AUTO"])


def test_animation_has_keyframes():
    assert "keyframe_insert" in animation_script(30, 2)
