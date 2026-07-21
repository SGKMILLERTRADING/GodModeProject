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

ue_script = """import unreal, os

log_path = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder/ue_debug.log"
with open(log_path, "w") as f:
    try:
        rt = unreal.RenderingLibrary.create_render_target2d(None, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        loc, rot = unreal.Vector(0, 0, 100), unreal.Rotator(0, 0, 0)
        try:
            cam_info = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
            if cam_info:
                loc, rot = cam_info[0], cam_info[1]
        except Exception:
            pass
            
        capture_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, loc)
        if capture_actor:
            capture_actor.set_actor_rotation(rot, False)
            comp = capture_actor.get_component_by_class(unreal.SceneCaptureComponent2D)
            if comp:
                comp.set_editor_property("texture_target", rt)
                comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
                comp.capture_scene()
                
                target_dir = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder"
                # Export with file_name="shot"
                unreal.RenderingLibrary.export_render_target(None, rt, target_dir, "shot")
                
            unreal.EditorLevelLibrary.destroy_actor(capture_actor)
            
        sync_dir = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder"
        files = os.listdir(sync_dir)
        f.write(f"Files in SyncFolder after export: {files}\\n")
    except Exception as ex:
        f.write(f"Error: {ex}\\n")
"""

print("Executing Offscreen RenderTarget Export test...")
res = send_request("execute_unreal_python", {"script": ue_script})
print("Result:", res)

log_file = r"C:\Users\sassy\OneDrive\Desktop\Unreal and Blender plugin and extension\SyncFolder\ue_debug.log"
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        print("\n--- DEBUG LOG ---")
        print(f.read())
