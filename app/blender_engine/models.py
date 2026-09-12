from __future__ import annotations
from enum import StrEnum
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Vec3 = tuple[float, float, float]


class OperationName(StrEnum):
    IMPORT_MODEL = "import_model"
    MODIFY_MESH = "modify_mesh"
    CREATE_MATERIAL = "create_material"
    ASSIGN_TEXTURE = "assign_texture"
    CREATE_ARMATURE = "create_armature"
    CREATE_BONE = "create_bone"
    BIND_MESH = "bind_mesh"
    CREATE_SHAPE_KEY = "create_shape_key"
    ADD_KEYFRAME = "add_keyframe"
    CREATE_CAMERA = "create_camera"
    CREATE_LIGHT = "create_light"
    SET_RENDER_SETTINGS = "set_render_settings"
    RENDER = "render"
    EXPORT = "export"


class StrictOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ImportModel(StrictOperation):
    operation: Literal["import_model"]
    asset_key: str = Field(pattern=r"^[A-Za-z0-9_./-]+$", max_length=512)


class ModifyMesh(StrictOperation):
    operation: Literal["modify_mesh"]
    object_name: str = Field(max_length=128)
    weld_distance: float = Field(default=1e-5, ge=0, le=0.01)
    recalculate_normals: bool = True
    smooth: bool = True


class CreateMaterial(StrictOperation):
    operation: Literal["create_material"]
    name: str = Field(max_length=128)
    base_color: tuple[float, float, float, float]
    metallic: float = Field(ge=0, le=1)
    roughness: float = Field(ge=0, le=1)


class AssignTexture(StrictOperation):
    operation: Literal["assign_texture"]
    material: str = Field(max_length=128)
    channel: Literal["Base Color", "Normal", "Roughness", "Metallic", "Emission", "Alpha", "AO"]
    asset_key: str = Field(pattern=r"^[A-Za-z0-9_./-]+$", max_length=512)


class CreateBone(StrictOperation):
    operation: Literal["create_bone"]
    armature: str = Field(max_length=128)
    name: str = Field(max_length=128)
    head: Vec3
    tail: Vec3
    parent: str | None = None

    @model_validator(mode="after")
    def nonzero(self):
        if self.head == self.tail:
            raise ValueError("bone length must be non-zero")
        return self


class AddKeyframe(StrictOperation):
    operation: Literal["add_keyframe"]
    target: str = Field(max_length=128)
    frame: int = Field(ge=0, le=100000)
    property: Literal["location", "rotation_euler", "scale", "value"]
    value: tuple[float, ...] = Field(min_length=1, max_length=4)


class CreateCamera(StrictOperation):
    operation: Literal["create_camera"]
    name: str = Field(default="Camera", max_length=128)
    position: Vec3
    rotation: Vec3
    focal_length: float = Field(default=50, ge=1, le=500)


class CreateLight(StrictOperation):
    operation: Literal["create_light"]
    name: str = Field(default="Light", max_length=128)
    light_type: Literal["AREA", "POINT", "SUN", "SPOT"]
    energy: float = Field(ge=0, le=100000)
    position: Vec3
    rotation: Vec3 = (0, 0, 0)


class RenderSettings(StrictOperation):
    operation: Literal["set_render_settings"]
    engine: Literal["BLENDER_EEVEE_NEXT", "CYCLES"]
    width: int = Field(ge=64, le=7680)
    height: int = Field(ge=64, le=7680)
    fps: Literal[24, 30, 60]
    samples: int = Field(ge=1, le=4096)


class Render(StrictOperation):
    operation: Literal["render"]
    output_key: str = Field(pattern=r"^[A-Za-z0-9_./-]+$", max_length=512)
    animation: bool = False


class Export(StrictOperation):
    operation: Literal["export"]
    output_key: str = Field(pattern=r"^[A-Za-z0-9_./-]+$", max_length=512)
    format: Literal["GLB", "GLTF", "FBX", "BLEND"]


Operation = Annotated[
    Union[ImportModel, ModifyMesh, CreateMaterial, AssignTexture, CreateBone, AddKeyframe, CreateCamera, CreateLight, RenderSettings, Render, Export],
    Field(discriminator="operation"),
]


class BlenderPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    project_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    operations: list[Operation] = Field(min_length=1, max_length=10000)

    @field_validator("operations")
    @classmethod
    def render_last(cls, value: list[Operation]):
        terminal = {"render", "export"}
        if any(op.operation in terminal for op in value[:-1]):
            raise ValueError("render/export must be the final operation")
        return value
