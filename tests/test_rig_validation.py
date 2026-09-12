from app.blender.rig_validation import REQUIRED_BONES, rig_validation_script


def test_deformation_pose_validation():
    assert {"head", "hand.L", "foot.R"} <= REQUIRED_BONES
    assert "keyframe_insert" in rig_validation_script() and "weights missing" in rig_validation_script()
