from __future__ import annotations
import json
from pathlib import Path
from app.blender.scripts import import_statement


def refinement_script(source: Path, work_dir: Path, rig_required: bool = False) -> str:
    """Create a Blender-side cleanup/QC script. It fails closed before exports."""
    blend = work_dir / "Character.blend"
    glb = work_dir / "Character.glb"
    report = work_dir / "quality.json"
    previews = work_dir / "previews"
    return f"""import bpy, bmesh, json, math
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
{import_statement(str(source))}
issues=[]; repairs=[]
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
if not meshes: raise RuntimeError('QC: reconstructed mesh missing')
for obj in meshes:
 bpy.context.view_layer.objects.active=obj; obj.select_set(True)
 bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
 bm=bmesh.new(); bm.from_mesh(obj.data)
 bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=0.00001)
 bmesh.ops.recalc_face_normals(bm,faces=bm.faces); bm.to_mesh(obj.data); bm.free(); repairs += ['duplicates','normals']
 if not obj.data.uv_layers:
  bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(island_margin=0.02); bpy.ops.object.mode_set(mode='OBJECT'); repairs.append('uv')
 for polygon in obj.data.polygons: polygon.use_smooth=True
 obj.select_set(False)
# True 3D guard: reject cards and degenerate meshes using world bounding-box thickness and signed volume.
dims=[]; volume=0.0
for obj in meshes:
 dims.extend(abs(v) for v in obj.dimensions)
 bm=bmesh.new(); bm.from_mesh(obj.data); volume += abs(bm.calc_volume(signed=False)); bm.free()
if min(dims,default=0)<0.005 or volume<1e-6: issues.append('mesh has no usable volume (plane/billboard/degenerate)')
if not any(o.data.uv_layers for o in meshes): issues.append('UV missing')
if not any(o.data.materials for o in meshes): issues.append('materials missing')
if {rig_required!r} and not any(o.type=='ARMATURE' for o in bpy.context.scene.objects): issues.append('armature missing')
# Preview turntable from the same current model.
bpy.ops.object.camera_add(); camera=bpy.context.object; bpy.context.scene.camera=camera
bpy.ops.object.light_add(type='AREA',location=(4,-4,6)); bpy.context.object.data.energy=1200; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=5
center=sum((o.matrix_world.translation for o in meshes),Vector())/len(meshes); radius=max(max(o.dimensions) for o in meshes)*2.5
for label,angle in [('front',0),('side',math.pi/2),('back',math.pi),('three_quarter',math.pi/4)]:
 camera.location=center+Vector((math.sin(angle)*radius,-math.cos(angle)*radius,radius*.25)); camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
 bpy.context.scene.render.filepath={json.dumps(str(previews))}+'/'+label+'.png'; bpy.context.scene.render.resolution_x=512; bpy.context.scene.render.resolution_y=512; bpy.context.scene.render.resolution_percentage=100
 bpy.ops.render.render(write_still=True)
with open({json.dumps(str(report))},'w',encoding='utf-8') as f: json.dump({{'issues':issues,'repairs':sorted(set(repairs)),'mesh_count':len(meshes),'volume':volume}},f)
if issues: raise RuntimeError('Quality control failed: '+', '.join(issues))
bpy.ops.wm.save_as_mainfile(filepath={json.dumps(str(blend))})
bpy.ops.export_scene.gltf(filepath={json.dumps(str(glb))},export_format='GLB')
"""
