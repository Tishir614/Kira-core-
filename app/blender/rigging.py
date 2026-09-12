from dataclasses import dataclass


@dataclass(frozen=True)
class RigOptions:
    blink: bool = True
    ears: bool = True
    tail: bool = True
    mouth: bool = True


def rig_script(options: RigOptions) -> str:
    """Generate a deterministic humanoid/furry control rig; mesh fitting still requires suitable topology."""
    extras: list[tuple[str, tuple[float, float, float], tuple[float, float, float], str]] = []
    if options.ears:
        extras += [("ear.L", (0, 0, 1.7), (0.25, 0, 1.95), "head"), ("ear.R", (0, 0, 1.7), (-0.25, 0, 1.95), "head")]
    if options.tail:
        extras += [("tail.01", (0, 0.15, 0.9), (0, 0.5, 0.7), "hips"), ("tail.02", (0, 0.5, 0.7), (0, 0.8, 0.55), "tail.01")]
    bones = [
        ("hips", (0, 0, 0.9), (0, 0, 1.15), None),
        ("spine", (0, 0, 1.15), (0, 0, 1.5), "hips"),
        ("head", (0, 0, 1.5), (0, 0, 1.8), "spine"),
        ("arm.L", (0, 0, 1.45), (0.65, 0, 1.35), "spine"),
        ("arm.R", (0, 0, 1.45), (-0.65, 0, 1.35), "spine"),
        ("leg.L", (0.15, 0, 0.9), (0.15, 0, 0.1), "hips"),
        ("leg.R", (-0.15, 0, 0.9), (-0.15, 0, 0.1), "hips"),
    ] + extras
    return "import bpy\n" + f"bones={bones!r}\n" + """bpy.ops.object.armature_add(enter_editmode=True); rig=bpy.context.object; rig.name='KiraRig'
base=rig.data.edit_bones[0]; rig.data.edit_bones.remove(base)
for name,head,tail,parent in bones:
 b=rig.data.edit_bones.new(name); b.head=head; b.tail=tail
 if parent: b.parent=rig.data.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
for obj in [o for o in bpy.context.scene.objects if o.type=='MESH']:
 obj.select_set(True); rig.select_set(True); bpy.context.view_layer.objects.active=rig
 bpy.ops.object.parent_set(type='ARMATURE_AUTO'); obj.select_set(False)
"""


def animation_script(fps: int = 30, duration: float = 4) -> str:
    frames = max(2, round(fps * duration))
    return f"""scene=bpy.context.scene; scene.render.fps={fps}; scene.frame_end={frames}
rig=bpy.data.objects.get('KiraRig')
if not rig: raise RuntimeError('Rig is required before animation')
for frame,angle in [(1,0),({frames//4},0.12),({frames//2},0),({frames*3//4},-0.12),({frames},0)]:
 scene.frame_set(frame); rig.rotation_euler[2]=angle; rig.keyframe_insert('rotation_euler',index=2)
if rig.pose.bones.get('head'):
 for frame,angle in [(1,-0.05),({frames//2},0.08),({frames},-0.05)]:
  rig.pose.bones['head'].rotation_mode='XYZ'; rig.pose.bones['head'].rotation_euler[0]=angle; rig.pose.bones['head'].keyframe_insert('rotation_euler',frame=frame)
"""
