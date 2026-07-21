import socket
import json
import os

AUTH_TOKEN = "d9a7f3e8b6c04a92a5f2e1c4b9d7e3a1"

def send_request(action, params={}):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 8001))
    req = {
        "auth_token": AUTH_TOKEN,
        "action": action,
        **params
    }
    s.sendall(json.dumps(req).encode("utf-8"))
    
    chunks = []
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
        try:
            res = json.loads(b"".join(chunks).decode("utf-8"))
            s.close()
            return res
        except json.JSONDecodeError:
            continue
    s.close()
    return None

shot_target = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder/ue_screenshot.png"
if os.path.exists(shot_target):
    os.remove(shot_target)

ue_script = """import unreal, os

log_path = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder/ue_debug.log"
with open(log_path, "w") as f:
    try:
        # Create RenderTarget
        rt = unreal.RenderingLibrary.create_render_target2d(None, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        
        # Get viewport camera location & rotation
        loc, rot = unreal.Vector(0, 0, 100), unreal.Rotator(0, 0, 0)
        try:
            cam_info = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
            if cam_info:
                loc, rot = cam_info[0], cam_info[1]
                f.write(f"Viewport camera: loc={loc}, rot={rot}\\n")
        except Exception as e:
            f.write(f"Could not get viewport camera: {e}\\n")
            
        # Spawn SceneCapture2D actor
        capture_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, loc)
        if capture_actor:
            capture_actor.set_actor_rotation(rot, False)
            comp = capture_actor.get_component_by_class(unreal.SceneCaptureComponent2D)
            if comp:
                comp.set_editor_property("texture_target", rt)
                comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
                comp.capture_scene()
                
                target_dir = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder"
                unreal.RenderingLibrary.export_render_target(None, rt, target_dir, "ue_screenshot.png")
                f.write("Exported render target to ue_screenshot.png successfully!\\n")
                
            unreal.EditorLevelLibrary.destroy_actor(capture_actor)
    except Exception as ex:
        f.write(f"Offscreen capture error: {ex}\\n")
"""

print("Executing Offscreen Capture via Python...")
res = send_request("execute_unreal_python", {"script": ue_script})
print("Result:", res)

# Check if file was created
if os.path.exists(shot_target):
    print("SUCCESS: Offscreen capture created ue_screenshot.png! Size:", os.path.getsize(shot_target))
else:
    print("FAILED: Offscreen capture file missing")
    
log_file = r"C:\Users\sassy\OneDrive\Desktop\Unreal and Blender plugin and extension\SyncFolder\ue_debug.log"
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        print("\n--- DEBUG LOG ---")
        print(f.read())
