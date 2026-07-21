import socket
import json

BLENDER_HOST = "127.0.0.1"
BLENDER_PORT = 12345

def send_to_blender(command: dict) -> dict:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect((BLENDER_HOST, BLENDER_PORT))
            s.sendall(json.dumps(command).encode('utf-8'))
            s.shutdown(socket.SHUT_WR)
            
            chunks = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            data = b''.join(chunks)
            if not data:
                return {"status": "error", "message": "No response"}
            return json.loads(data.decode('utf-8'))
    except Exception as e:
        return {"status": "error", "message": str(e)}

print(send_to_blender({"action": "get_scene_hierarchy"}))
