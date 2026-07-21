import json
import os
import bpy

# Basic mapping from Rigify (meta-rig or generated rig) to UE5 Mannequin
RIGIFY_TO_UE5 = {
    "spine": "spine_01",
    "spine.001": "spine_02",
    "spine.002": "spine_03",
    "spine.003": "spine_04",
    "spine.004": "neck_01",
    "spine.005": "neck_02",
    "spine.006": "head",
    "pelvis": "pelvis",
    
    "shoulder.L": "clavicle_l",
    "upper_arm.L": "upperarm_l",
    "forearm.L": "lowerarm_l",
    "hand.L": "hand_l",
    
    "shoulder.R": "clavicle_r",
    "upper_arm.R": "upperarm_r",
    "forearm.R": "lowerarm_r",
    "hand.R": "hand_r",
    
    "thigh.L": "thigh_l",
    "shin.L": "calf_l",
    "foot.L": "foot_l",
    "toe.L": "ball_l",
    
    "thigh.R": "thigh_r",
    "shin.R": "calf_r",
    "foot.R": "foot_r",
    "toe.R": "ball_r"
}

def export_retarget_config(objects, filepath):
    """Exports a bone mapping config to JSON if an armature is found."""
    armatures = [obj for obj in objects if obj.type == 'ARMATURE']
    if not armatures:
        return
        
    # Just grab the first armature for now
    armature = armatures[0]
    
    config = {
        "armature_name": armature.name,
        "mapping_type": "rigify_to_ue5",
        "bone_mapping": RIGIFY_TO_UE5
    }
    
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=4)
        
    return config
