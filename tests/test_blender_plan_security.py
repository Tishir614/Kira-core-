import pytest

pydantic = pytest.importorskip("pydantic", minversion="2")
from app.blender_engine.models import BlenderPlan


def test_rejects_code_and_unknown_fields():
    with pytest.raises(Exception):
        BlenderPlan.model_validate(
            {"schema_version": 1, "project_id": "00000000-0000-0000-0000-000000000000", "operations": [{"operation": "exec", "code": 'os.system("id")'}]}
        )


def test_rejects_path_traversal():
    with pytest.raises(Exception):
        BlenderPlan.model_validate(
            {
                "schema_version": 1,
                "project_id": "00000000-0000-0000-0000-000000000000",
                "operations": [{"operation": "import_model", "asset_key": "../../etc/passwd"}],
            }
        )


@pytest.mark.parametrize("path", ["/etc/passwd", "../secret.glb", "models/../../secret.glb", "~/.ssh/id_rsa", "\\server\\share"])
def test_rejects_all_non_project_asset_paths(path):
    with pytest.raises(Exception):
        BlenderPlan.model_validate(
            {
                "schema_version": 1,
                "project_id": "00000000-0000-0000-0000-000000000000",
                "operations": [{"operation": "import_model", "asset_key": path}],
            }
        )


def test_valid_light_plan():
    plan = BlenderPlan.model_validate(
        {
            "schema_version": 1,
            "project_id": "00000000-0000-0000-0000-000000000000",
            "operations": [{"operation": "create_light", "light_type": "AREA", "energy": 800, "position": [2, -3, 4]}],
        }
    )
    assert plan.operations[0].energy == 800
