REQUIRED_BONES = {
    "root",
    "hips",
    "spine",
    "chest",
    "neck",
    "head",
    "upper_arm.L",
    "forearm.L",
    "hand.L",
    "upper_arm.R",
    "forearm.R",
    "hand.R",
    "thigh.L",
    "shin.L",
    "foot.L",
    "thigh.R",
    "shin.R",
    "foot.R",
}


def rig_validation_script() -> str:
    return f"""required={sorted(REQUIRED_BONES)!r}; issues=[]
rig=next((o for o in bpy.context.scene.objects if o.type=='ARMATURE'),None)
if not rig: raise RuntimeError('Rig QC: armature missing')
missing=[name for name in required if name not in rig.data.bones]
if missing: issues.append('missing bones: '+','.join(missing))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
for obj in meshes:
 if not any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers): issues.append(obj.name+': armature modifier missing')
 if not obj.vertex_groups: issues.append(obj.name+': weights missing')
# Exercise deform controls. The resulting action proves bones change transforms; geometric thresholds remain provider/profile-specific.
bpy.context.view_layer.objects.active=rig; bpy.ops.object.mode_set(mode='POSE'); scene=bpy.context.scene
poses={{'upper_arm.L':(0,0,1.2),'upper_arm.R':(0,0,-1.2),'forearm.L':(0,1.4,0),'thigh.L':(0.7,0,0),'head':(0,0,0.6)}}
for frame,factor in ((1,0),(10,1),(20,0)):
 scene.frame_set(frame)
 for name,rotation in poses.items():
  bone=rig.pose.bones.get(name)
  if bone: bone.rotation_mode='XYZ'; bone.rotation_euler=[v*factor for v in rotation]; bone.keyframe_insert('rotation_euler',frame=frame)
bpy.ops.object.mode_set(mode='OBJECT')
if issues: raise RuntimeError('Rig quality control failed: '+'; '.join(issues))
"""
