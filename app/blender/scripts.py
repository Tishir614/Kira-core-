from __future__ import annotations
import json
from pathlib import Path

SUPPORTED = {".glb", ".gltf", ".fbx", ".obj", ".blend"}


def _literal(value: str) -> str:
    return json.dumps(str(Path(value).resolve()))


def import_statement(path: str) -> str:
    ext = Path(path).suffix.lower()
    p = _literal(path)
    if ext not in SUPPORTED:
        raise ValueError(f"Blender import is unsupported: {ext}")
    return {
        ".glb": f"bpy.ops.import_scene.gltf(filepath={p})",
        ".gltf": f"bpy.ops.import_scene.gltf(filepath={p})",
        ".fbx": f"bpy.ops.import_scene.fbx(filepath={p})",
        ".obj": f"bpy.ops.wm.obj_import(filepath={p})",
        ".blend": f"bpy.ops.wm.open_mainfile(filepath={p})",
    }[ext]


def smoke_script(output: str) -> str:
    return f"""import bpy
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(location=(0,0,0))
bpy.ops.object.camera_add(location=(4,-4,3)); camera=bpy.context.object; bpy.context.scene.camera=camera
camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.light_add(type='AREA', location=(2,-2,4)); bpy.context.object.data.energy=1000
bpy.context.scene.render.engine='BLENDER_EEVEE_NEXT'
bpy.context.scene.render.resolution_x=256; bpy.context.scene.render.resolution_y=256; bpy.context.scene.render.resolution_percentage=100
bpy.context.scene.render.filepath={_literal(output)}
bpy.ops.render.render(write_still=True)
"""


def project_script(source: str, output_blend: str) -> str:
    return f"""import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
{import_statement(source)}
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        for poly in obj.data.polygons: poly.use_smooth=True
bpy.ops.wm.save_as_mainfile(filepath={_literal(output_blend)})
"""
