from __future__ import annotations
import json
from pathlib import Path
from app.blender_engine.models import BlenderPlan


class BlenderPlanExecutor:
    def __init__(self, project_root: Path, logger):
        self.root = project_root.resolve()
        self.log = logger

    def path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("path escapes project")
        return candidate

    def execute(self, plan: BlenderPlan) -> None:
        import bpy, bmesh

        for index, op in enumerate(plan.operations):
            self.log.info("blender_operation", extra={"operation": op.operation, "operation_index": index})
            match op.operation:
                case "import_model":
                    self._import(bpy, self.path(op.asset_key))
                case "modify_mesh":
                    obj = bpy.data.objects.get(op.object_name)
                    if not obj or obj.type != "MESH":
                        raise RuntimeError(f"mesh not found: {op.object_name}")
                    bm = bmesh.new()
                    bm.from_mesh(obj.data)
                    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=op.weld_distance)
                    if op.recalculate_normals:
                        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
                    bm.to_mesh(obj.data)
                    bm.free()
                    if op.smooth:
                        for face in obj.data.polygons:
                            face.use_smooth = True
                case "create_material":
                    mat = bpy.data.materials.new(op.name)
                    mat.diffuse_color = op.base_color
                    mat.metallic = op.metallic
                    mat.roughness = op.roughness
                case "create_camera":
                    bpy.ops.object.camera_add(location=op.position, rotation=op.rotation)
                    bpy.context.object.name = op.name
                    bpy.context.object.data.lens = op.focal_length
                    bpy.context.scene.camera = bpy.context.object
                case "create_light":
                    bpy.ops.object.light_add(type=op.light_type, location=op.position, rotation=op.rotation)
                    bpy.context.object.name = op.name
                    bpy.context.object.data.energy = op.energy
                case "set_render_settings":
                    scene = bpy.context.scene
                    scene.render.engine = op.engine
                    scene.render.resolution_x = op.width
                    scene.render.resolution_y = op.height
                    scene.render.fps = op.fps
                    scene.render.image_settings.file_format = "PNG"
                    scene.render.resolution_percentage = 100
                    if op.engine == "CYCLES":
                        scene.cycles.samples = op.samples
                case "add_keyframe":
                    target = bpy.data.objects.get(op.target)
                    if not target:
                        raise RuntimeError(f"target not found: {op.target}")
                    setattr(target, op.property, op.value if len(op.value) > 1 else op.value[0])
                    target.keyframe_insert(data_path=op.property, frame=op.frame)
                case "render":
                    output = self.path(op.output_key)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    bpy.context.scene.render.filepath = str(output)
                    bpy.ops.render.render(animation=op.animation, write_still=not op.animation)
                case "export":
                    self._export(bpy, op.format, self.path(op.output_key))
                case _:
                    raise RuntimeError(f"operation is validated but not enabled by this worker: {op.operation}")

    def _import(self, bpy, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(path)
        suffix = path.suffix.lower()
        if suffix in {".glb", ".gltf"}:
            bpy.ops.import_scene.gltf(filepath=str(path))
        elif suffix == ".fbx":
            bpy.ops.import_scene.fbx(filepath=str(path))
        elif suffix == ".obj":
            bpy.ops.wm.obj_import(filepath=str(path))
        elif suffix == ".blend":
            bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
        else:
            raise ValueError("unsupported model format")

    def _export(self, bpy, format: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if format == "BLEND":
            bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)
        elif format in {"GLB", "GLTF"}:
            bpy.ops.export_scene.gltf(filepath=str(path), export_format=format)
        elif format == "FBX":
            bpy.ops.export_scene.fbx(filepath=str(path), use_selection=False)
