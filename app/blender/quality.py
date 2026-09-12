from dataclasses import dataclass


@dataclass(frozen=True)
class QualityRequest:
    rig_required: bool = False
    animation_required: bool = False


def blender_quality_script(request: QualityRequest) -> str:
    return f"""issues=[]
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
if not meshes: issues.append('mesh missing')
if meshes and not any(o.data.materials for o in meshes): issues.append('materials missing')
if {request.rig_required!r} and not any(o.type=='ARMATURE' for o in bpy.context.scene.objects): issues.append('armature missing')
if {request.animation_required!r} and not any(o.animation_data and o.animation_data.action for o in bpy.context.scene.objects): issues.append('animation missing')
if bpy.context.scene.camera is None: issues.append('camera missing')
if issues: raise RuntimeError('Quality control failed: '+', '.join(issues))
"""
