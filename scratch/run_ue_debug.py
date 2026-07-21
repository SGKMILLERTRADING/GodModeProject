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
    
    # Read response
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

# First disable throttling
print("Disabling background throttling...")
send_request("execute_unreal_python", {
    "script": "import unreal; unreal.SystemLibrary.execute_console_command(None, 't.IdleWhenNotForeground 0')"
})

# Now queue a screenshot
print("Queueing screenshot...")
target_shot = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder/ue_screenshot.png"
if os.path.exists(target_shot):
    os.remove(target_shot)

send_request("execute_unreal_python", {
    "script": f"import unreal; unreal.AutomationLibrary.take_high_res_screenshot(1280, 720, '{target_shot}')"
})

# Wait for 3 seconds in our process
print("Waiting for rendering thread...")
time.sleep(3.0)

if os.path.exists(target_shot):
    print("SUCCESS: ue_screenshot.png exists! Size:", os.path.getsize(target_shot))
else:
    print("FAILED: ue_screenshot.png does not exist")
