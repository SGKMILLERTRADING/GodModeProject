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
def log(msg):
    with open(log_path, "a") as f:
        f.write(str(msg) + "\\n")

if os.path.exists(log_path):
    os.remove(log_path)

log("Starting export_texture2d test")
try:
    rt = unreal.RenderingLibrary.create_render_target2d(None, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    log("Created RT")
    
    cam_loc, cam_rot = unreal.Vector(0, 0, 100), unreal.Rotator(0, 0, 0)
    capture_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, cam_loc)
    log(f"Spawned capture actor: {capture_actor}")
    
    if capture_actor:
        comp = capture_actor.get_component_by_class(unreal.SceneCaptureComponent2D)
        log(f"Component: {comp}")
        if comp:
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
            comp.capture_scene()
            log("Captured scene")

        tex = unreal.RenderingLibrary.render_target_create_static_texture2d_editor_only(rt, "TempShotTex")
        log(f"Created static tex: {tex}")
        
        if tex:
            target_dir = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder"
            log("Calling export_texture2d")
            unreal.RenderingLibrary.export_texture2d(None, tex, target_dir, "ue_screenshot.png")
            log("Export call done")
            
        unreal.EditorLevelLibrary.destroy_actor(capture_actor)
except Exception as ex:
    log(f"Error: {ex}")
"""

print("Executing detailed export_texture2d test...")
res = send_request("execute_unreal_python", {"script": ue_script})

log_file = r"C:\Users\sassy\OneDrive\Desktop\Unreal and Blender plugin and extension\SyncFolder\ue_debug.log"
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        print("\n--- DEBUG LOG ---")
        print(f.read())
