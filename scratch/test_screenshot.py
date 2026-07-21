import http.client
import json
import os
import time

AUTH_TOKEN = "d9a7f3e8b6c04a92a5f2e1c4b9d7e3a1"
UNREAL_HOST = "127.0.0.1"
UNREAL_PORT = 30010

def unreal_remote(endpoint, payload):
    conn = http.client.HTTPConnection(UNREAL_HOST, UNREAL_PORT, timeout=5)
    headers = {"Content-Type": "application/json"}
    body = {"objectPath": payload.get("objectPath"), "functionName": payload.get("functionName"), "parameters": payload.get("parameters"), "generateTransaction": True}
    
    try:
        conn.request("PUT", endpoint, json.dumps(body), headers)
        resp = conn.getresponse()
        data = resp.read()
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Execute via Kismet to write a test file
test_file = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder/py_works.txt"
if os.path.exists(test_file):
    os.remove(test_file)

result = unreal_remote("/remote/object/call", {
    "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
    "functionName": "ExecuteConsoleCommand",
    "parameters": {
        "WorldContextObject": None,
        "Command": f'py "open(\'{test_file}\', \'w\').write(\'hello\')"'
    }
})

print("Kismet response:", result)

time.sleep(2)
if os.path.exists(test_file):
    print("SUCCESS: Python executed and wrote file!")
else:
    print("FAILED: Python did not write file.")
