import subprocess
import json
import sys

def test_bridge(script_path):
    print(f"Testing {script_path}")
    proc = subprocess.Popen(
        [r"C:\Python314\python.exe", "-X", "utf8", script_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }
    
    try:
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()
    except Exception as e:
        print(f"Failed to write to stdin: {e}")
        return
        
    try:
        out = proc.stdout.readline()
        if not out:
            print("Process exited immediately without output")
            print("STDERR:", proc.stderr.read())
        else:
            print("Received response:", out.strip())
    except Exception as e:
        print(f"Failed to read stdout: {e}")
        
    proc.terminate()

test_bridge(r"C:\Users\sassy\OneDrive\Desktop\Unreal and Blender plugin and extension\unreal_mcp_bridge.py")
test_bridge(r"C:\Users\sassy\OneDrive\Desktop\Unreal and Blender plugin and extension\blender_mcp_bridge.py")
