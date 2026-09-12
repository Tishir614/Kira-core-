import pytest
from app.blender.scripts import import_statement


@pytest.mark.parametrize(
    "name,operator",
    [
        ("a.glb", "import_scene.gltf"),
        ("a.gltf", "import_scene.gltf"),
        ("a.fbx", "import_scene.fbx"),
        ("a.obj", "wm.obj_import"),
        ("a.blend", "wm.open_mainfile"),
    ],
)
def test_importers(name, operator):
    assert operator in import_statement(name)


def test_reject_script():
    with pytest.raises(ValueError):
        import_statement("evil.py")
