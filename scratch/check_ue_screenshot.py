import socket
import json

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

ue_script = """import unreal, os, glob
proj_saved = unreal.Paths.project_saved_dir()
screenshots_dir = os.path.abspath(os.path.join(proj_saved, "Screenshots"))
unreal.log(f"SAVED SCREENSHOTS DIR: {screenshots_dir}")
exists = os.path.exists(screenshots_dir)
unreal.log(f"DIR EXISTS: {exists}")
if exists:
    png_files = glob.glob(os.path.join(screenshots_dir, "**", "*.png"), recursive=True)
    unreal.log(f"PNG FILES: {png_files}")
"""

print("Executing Unreal Python check...")
res = send_request("execute_unreal_python", {"script": ue_script})
print("Result:", res)
