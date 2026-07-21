import bpy
import socket
import json
import math

UDP_IP = "127.0.0.1"
UDP_PORT = 8002
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

_is_live_link_active = False

def get_object_data(obj):
    """Extracts transform and specific properties based on object type."""
    # Convert Blender Z-up to Unreal Z-up
    # Blender +X, +Y, +Z -> Unreal +X, -Y, +Z (Roughly, or we just send raw and let Unreal decode it)
    # We will send raw Blender matrix or euler, and let Unreal handle conversion to avoid complex math here.
    
    loc = obj.matrix_world.translation
    rot = obj.matrix_world.to_euler()
    scl = obj.matrix_world.to_scale()
    
    data = {
        "name": obj.name,
        "type": obj.type,
        "location": [loc.x, loc.y, loc.z],
        "rotation": [rot.x, rot.y, rot.z],
        "scale": [scl.x, scl.y, scl.z],
    }
    
    if obj.type == 'CAMERA' and obj.data:
        data["fov"] = math.degrees(obj.data.angle)
    
    elif obj.type == 'LIGHT' and obj.data:
        data["energy"] = obj.data.energy
        data["color"] = [obj.data.color[0], obj.data.color[1], obj.data.color[2]]
        
    return data

def depsgraph_update_handler(scene, depsgraph):
    """Fired when objects update in the viewport."""
    global _is_live_link_active
    if not _is_live_link_active:
        return
        
    updates = []
    for update in depsgraph.updates:
        if update.is_updated_transform or update.is_updated_geometry:
            obj = update.id
            if isinstance(obj, bpy.types.Object):
                try:
                    updates.append(get_object_data(obj))
                except Exception as e:
                    print(f"LiveLink error on {obj.name}: {e}")
                
    if updates:
        payload = json.dumps({"action": "livelink_update", "objects": updates})
        try:
            sock.sendto(payload.encode('utf-8'), (UDP_IP, UDP_PORT))
        except Exception as e:
            print(f"LiveLink send error: {e}")

class UBSyncToggleLiveLinkOperator(bpy.types.Operator):
    bl_idname = "ubsync.toggle_livelink"
    bl_label = "Toggle Live Link"
    bl_description = "Start or stop sending real-time UDP updates to Unreal"

    def execute(self, context):
        global _is_live_link_active
        _is_live_link_active = not _is_live_link_active
        
        context.scene.ubsync_settings.livelink_active = _is_live_link_active
        
        if _is_live_link_active:
            self.report({'INFO'}, "Live Link Started (Port 8002)")
        else:
            self.report({'INFO'}, "Live Link Stopped")
            
        return {'FINISHED'}

def register():
    bpy.utils.register_class(UBSyncToggleLiveLinkOperator)
    if depsgraph_update_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_handler)

def unregister():
    bpy.utils.unregister_class(UBSyncToggleLiveLinkOperator)
    if depsgraph_update_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_handler)
