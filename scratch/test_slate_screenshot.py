import socket
import json
import os
import time

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

target_shot = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder/ue_screenshot.png"
if os.path.exists(target_shot):
    try:
        os.remove(target_shot)
    except Exception:
        pass

# Enable game view & disable background throttling
try:
    unreal.EditorLevelLibrary.editor_set_game_view(True)
except Exception:
    pass

unreal.SystemLibrary.execute_console_command(None, "t.IdleWhenNotForeground 0")
unreal.AutomationLibrary.take_high_res_screenshot(1280, 720, target_shot)

log_path = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder/ue_debug.log"
with open(log_path, "w") as f:
    f.write("Slate screenshot registered successfully\\n")
"""

print("Executing Slate Screenshot Registration via Python...")
res = send_request("execute_unreal_python", {"script": ue_script})
print("Result:", res)

# Wait up to 5 seconds for file creation in Python
found = False
for _ in range(50):
    if os.path.exists(shot_target) and os.path.getsize(shot_target) > 0:
        found = True
        break
    time.sleep(0.1)

if found:
    print("SUCCESS: ue_screenshot.png exists! Size:", os.path.getsize(shot_target))
else:
    print("FAILED: ue_screenshot.png missing")
