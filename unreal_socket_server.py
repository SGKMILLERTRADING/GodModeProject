"""
Unreal Socket Server
--------------------
Run this script with Python BEFORE starting your AI client.
It listens on port 8000 for MCP bridge requests, then forwards them
to Unreal Engine's built-in Remote Control API (port 30010).

HOW TO START:
    python unreal_socket_server.py

REQUIREMENTS:
    1. Unreal Engine must be open
    2. In Unreal: Edit -> Plugins -> search "Remote Control API" -> Enable -> Restart UE
    3. This script must be running before the AI client makes tool calls

Nothing else needs to be compiled or installed.
"""

import socket
import json
import threading
import http.client
import os
import sys
import configparser

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "UnrealMCPConfig.ini")

def load_config():
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        config["Settings"] = {
            "ListenHost": "127.0.0.1",
            "ListenPort": "8001",
            "AuthToken": "d9a7f3e8b6c04a92a5f2e1c4b9d7e3a1",
            "UnrealHost": "127.0.0.1",
            "UnrealPort": "30010",
            "DropboxPath": r"C:\Dropbox",
            "GDrive1_Meshes": r"G:\My Drive\Meshes",
            "GDrive2_Skins": r"G:\My Drive\Skins",
            "GDrive3_Anims": r"G:\My Drive\Anims",
            "GDrive4_Audio": r"G:\My Drive\Audio",
            "AssetLibraryPath": r"C:\Assets"
        }
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
    else:
        config.read(CONFIG_FILE)
    return config

_config = load_config()

# ── Configuration ─────────────────────────────────────────────────────────────
LISTEN_HOST  = _config.get("Settings", "ListenHost", fallback="127.0.0.1")
LISTEN_PORT  = _config.getint("Settings", "ListenPort", fallback=8001)
AUTH_TOKEN   = _config.get("Settings", "AuthToken", fallback="d9a7f3e8b6c04a92a5f2e1c4b9d7e3a1")

UNREAL_HOST  = _config.get("Settings", "UnrealHost", fallback="127.0.0.1")
UNREAL_PORT  = _config.getint("Settings", "UnrealPort", fallback=30010)

DROPBOX_PATH = _config.get("Settings", "DropboxPath", fallback=r"C:\Dropbox")
GDRIVE1_MESHES = _config.get("Settings", "GDrive1_Meshes", fallback=r"G:\My Drive\Meshes")
GDRIVE2_SKINS = _config.get("Settings", "GDrive2_Skins", fallback=r"G:\My Drive\Skins")
GDRIVE3_ANIMS = _config.get("Settings", "GDrive3_Anims", fallback=r"G:\My Drive\Anims")
GDRIVE4_AUDIO = _config.get("Settings", "GDrive4_Audio", fallback=r"G:\My Drive\Audio")
ASSET_LIBRARY_PATH = _config.get("Settings", "AssetLibraryPath", fallback=r"C:\Assets")

SYNC_FOLDER  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SyncFolder")
os.makedirs(SYNC_FOLDER, exist_ok=True)
# ─────────────────────────────────────────────────────────────────────────────


def unreal_remote(endpoint: str, payload: dict) -> dict:
    """Call Unreal's Remote Control REST API."""
    body = json.dumps(payload).encode("utf-8")
    try:
        conn = http.client.HTTPConnection(UNREAL_HOST, UNREAL_PORT, timeout=8)
        conn.request("PUT", endpoint, body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="replace")
        conn.close()
        if raw.strip():
            return json.loads(raw)
        return {"status": "ok"}
    except ConnectionRefusedError:
        return {
            "status": "error",
            "message": (
                "Cannot reach Unreal Engine on port 30010. "
                "Make sure UE is open and the Remote Control API plugin is enabled "
                "(Edit -> Plugins -> Remote Control API -> Enable -> Restart UE)."
            )
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _exec_ue_script(script: str, action_name: str) -> dict:
    """Write a Python script to the sync folder and execute it inside Unreal."""
    temp_file = os.path.join(SYNC_FOLDER, f"temp_{action_name}.py")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(script)
    except Exception as e:
        return {"status": "error", "message": f"Failed to write temp script: {str(e)}"}

    temp_file_ue = temp_file.replace("\\", "/")
    result = unreal_remote("/remote/object/call", {
        "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
        "functionName": "ExecuteConsoleCommand",
        "parameters": {
            "WorldContextObject": None,
            "Command": f'py "{temp_file_ue}"'
        }
    })
    result["action"] = action_name
    return result


def handle_action(req: dict) -> dict:
    """Dispatch an MCP action to Unreal or the sync folder."""
    action = req.get("action", "")

    # ── Actor hierarchy ───────────────────────────────────────────────────────
    if action == "get_actor_hierarchy":
        ue_script = f"""import unreal, json
actors = unreal.EditorLevelLibrary.get_all_level_actors()
out = []
for a in actors:
    if a:
        loc = a.get_actor_location()
        out.append({{
            "name": a.get_actor_label(),
            "path": a.get_path_name(),
            "class": a.get_class().get_name(),
            "location": {{"x": loc.x, "y": loc.y, "z": loc.z}}
        }})
out_path = "{SYNC_FOLDER.replace('\\\\', '/')}/actor_hierarchy.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f)
"""
        _exec_ue_script(ue_script, "get_actor_hierarchy")
        h_file = os.path.join(SYNC_FOLDER, "actor_hierarchy.json")
        if os.path.exists(h_file):
            try:
                with open(h_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {"status": "ok", "actors": data}
            except Exception:
                pass
        result = unreal_remote("/remote/object/call", {
            "objectPath": "/Script/UnrealEd.Default__EditorActorSubsystem",
            "functionName": "GetAllLevelActors",
            "parameters": {}
        })
        return result

    # ── Create actor ─────────────────────────────────────────────────────────
    elif action == "create_actor":
        actor_class = req.get("class", "StaticMeshActor")
        name = req.get("name", "NewActor")
        loc = req.get("location", {"x": 0, "y": 0, "z": 0})
        
        ue_script = f"""import unreal
cls_name = "{actor_class}"
if "." not in cls_name and "/" not in cls_name:
    cls_name = f"/Script/Engine.{{cls_name}}"

actor_cls = unreal.load_object(None, cls_name) if "/" in cls_name else None
if not actor_cls:
    try:
        actor_cls = getattr(unreal, "{actor_class}")
    except Exception:
        pass

loc = unreal.Vector({loc.get('x', 0)}, {loc.get('y', 0)}, {loc.get('z', 0)})
actor = None
if actor_cls:
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_cls, loc)
if actor:
    actor.set_actor_label("{name}")
    unreal.log(f"create_actor: Spawned {name}")
else:
    unreal.log_warning(f"create_actor: Could not spawn class {actor_class}")
"""
        return _exec_ue_script(ue_script, "create_actor")

    # ── Delete actor ─────────────────────────────────────────────────────────
    elif action == "delete_actor":
        name = req.get("name", "")
        ue_script = f"""import unreal
target_name = "{name}"
actors = unreal.EditorLevelLibrary.get_all_level_actors()
destroyed_count = 0
for a in actors:
    if a and (a.get_actor_label() == target_name or a.get_path_name() == target_name or a.get_name() == target_name or target_name in a.get_name()):
        unreal.EditorLevelLibrary.destroy_actor(a)
        destroyed_count += 1
unreal.log(f"delete_actor: Destroyed {{destroyed_count}} actor(s) matching {{target_name}}")
"""
        return _exec_ue_script(ue_script, "delete_actor")

    # ── Set transform ─────────────────────────────────────────────────────────
    elif action == "set_transform":
        name = req.get("name", "")
        transform = req.get("transform", {})
        x = transform.get("x", transform.get("X", 0))
        y = transform.get("y", transform.get("Y", 0))
        z = transform.get("z", transform.get("Z", 0))
        
        rot = transform.get("rotation", transform.get("rot", {}))
        pitch = rot.get("pitch", rot.get("Pitch", transform.get("pitch", 0)))
        yaw = rot.get("yaw", rot.get("Yaw", transform.get("yaw", 0)))
        roll = rot.get("roll", rot.get("Roll", transform.get("roll", 0)))
        
        scale = transform.get("scale", transform.get("scl", {}))
        if isinstance(scale, (int, float)):
            sx, sy, sz = scale, scale, scale
        else:
            sx = scale.get("x", scale.get("X", transform.get("scale_x", 1)))
            sy = scale.get("y", scale.get("Y", transform.get("scale_y", 1)))
            sz = scale.get("z", scale.get("Z", transform.get("scale_z", 1)))

        ue_script = f"""import unreal
target_name = "{name}"
actors = unreal.EditorLevelLibrary.get_all_level_actors()
found = False
for a in actors:
    if a and (a.get_actor_label() == target_name or a.get_path_name() == target_name or a.get_name() == target_name or target_name in a.get_name()):
        a.set_actor_location(unreal.Vector({x}, {y}, {z}), False, True)
        if {pitch} != 0 or {yaw} != 0 or {roll} != 0:
            a.set_actor_rotation(unreal.Rotator({pitch}, {yaw}, {roll}), False)
        if {sx} != 1 or {sy} != 1 or {sz} != 1:
            a.set_actor_scale3d(unreal.Vector({sx}, {sy}, {sz}))
        unreal.log(f"set_transform: Updated {{target_name}} transform")
        found = True
        break
if not found:
    unreal.log_warning(f"set_transform: Could not find actor matching {{target_name}}")
"""
        return _exec_ue_script(ue_script, "set_transform")

    # ── Run console command ───────────────────────────────────────────────────
    elif action == "run_editor_command":
        command = req.get("command", "")
        result  = unreal_remote("/remote/object/call", {
            "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
            "functionName": "ExecuteConsoleCommand",
            "parameters": {
                "WorldContextObject": None,
                "Command": command
            }
        })
        return result

    # ── Get Actor Property ───────────────────────────────────────────────────
    elif action == "get_actor_property":
        object_path = req.get("objectPath", req.get("name", ""))
        property_name = req.get("propertyName", "")
        
        ue_script = f"""import unreal, json
target_name = "{object_path}"
prop_name = "{property_name}"

actors = unreal.EditorLevelLibrary.get_all_level_actors()
target_actor = None
for a in actors:
    if a and (a.get_actor_label() == target_name or a.get_path_name() == target_name or a.get_name() == target_name):
        target_actor = a
        break

if not target_actor:
    try:
        target_actor = unreal.find_object(None, target_name)
    except Exception:
        pass

val_str = "None"
if target_actor:
    try:
        if "." in prop_name:
            parts = prop_name.split(".")
            curr = target_actor
            for p in parts:
                curr = curr.get_editor_property(p)
            val_str = str(curr)
        else:
            val_str = str(target_actor.get_editor_property(prop_name))
        unreal.log(f"get_actor_property: {{prop_name}} = {{val_str}}")
    except Exception as e:
        unreal.log_warning(f"get_actor_property error: {{e}}")

out_path = "{SYNC_FOLDER.replace('\\\\', '/')}/prop_result.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({{"property": prop_name, "value": val_str}}, f)
"""
        _exec_ue_script(ue_script, "get_actor_property")
        p_file = os.path.join(SYNC_FOLDER, "prop_result.json")
        if os.path.exists(p_file):
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {"status": "ok", "property": data.get("property"), "value": data.get("value")}
            except Exception:
                pass
        return unreal_remote("/remote/object/property", {
            "objectPath": object_path,
            "access": "READ_ACCESS",
            "propertyName": property_name
        })

    # ── Set Actor Property ───────────────────────────────────────────────────
    elif action == "set_actor_property":
        object_path = req.get("objectPath", req.get("name", ""))
        property_name = req.get("propertyName", "")
        property_value = req.get("propertyValue", None)
        
        val_str = json.dumps(property_value)
        
        ue_script = f"""import unreal, json
target_name = "{object_path}"
prop_name = "{property_name}"
val = json.loads('''{val_str}''')

actors = unreal.EditorLevelLibrary.get_all_level_actors()
target_actor = None
for a in actors:
    if a and (a.get_actor_label() == target_name or a.get_path_name() == target_name or a.get_name() == target_name):
        target_actor = a
        break

if not target_actor:
    try:
        target_actor = unreal.find_object(None, target_name)
    except Exception:
        pass

if target_actor:
    try:
        if "." in prop_name:
            parts = prop_name.split(".")
            curr = target_actor
            for p in parts[:-1]:
                curr = curr.get_editor_property(p)
            curr.set_editor_property(parts[-1], val)
        else:
            target_actor.set_editor_property(prop_name, val)
        unreal.log(f"set_actor_property: Set {{prop_name}} on {{target_name}}")
    except Exception as e:
        unreal.log_warning(f"set_actor_property error on {{target_name}}: {{e}}")
else:
    unreal.log_warning(f"set_actor_property: Could not find object {{target_name}}")
"""
        return _exec_ue_script(ue_script, "set_actor_property")

    # ── Call Blueprint Function ──────────────────────────────────────────────
    elif action == "call_blueprint_function":
        object_path = req.get("objectPath", "")
        function_name = req.get("functionName", "")
        parameters = req.get("parameters", {})
        result = unreal_remote("/remote/object/call", {
            "objectPath": object_path,
            "functionName": function_name,
            "parameters": parameters
        })
        return result

    # ── Execute Unreal Python ──────────────────────────────────────────────────
    elif action == "execute_unreal_python":
        script = req.get("script", "")
        temp_file = os.path.join(SYNC_FOLDER, "temp_exec.py")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(script)
        except Exception as e:
            return {"status": "error", "message": f"Failed to write temp python file: {str(e)}"}
            
        temp_file_ue = temp_file.replace("\\\\", "/")
        result = unreal_remote("/remote/object/call", {
            "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
            "functionName": "ExecuteConsoleCommand",
            "parameters": {
                "WorldContextObject": None,
                "Command": f'py "{temp_file_ue}"'
            }
        })
        return result

    # ── Trigger sync (write a request file; Blender picks it up) ──────────────
    elif action == "trigger_sync":
        export_type = req.get("type", "ALL")
        req_path    = os.path.join(SYNC_FOLDER, "request.json")
        with open(req_path, "w") as f:
            json.dump({"action": "export", "type": export_type}, f)
        return {"status": "ok", "message": f"Sync request written ({export_type})"}

    # ── Read metadata ─────────────────────────────────────────────────────────
    elif action == "get_metadata":
        meta_path = os.path.join(SYNC_FOLDER, "UnrealMetadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                return {"status": "ok", "metadata": json.load(f)}
        return {"status": "ok", "metadata": {}}

    # ── Write metadata ────────────────────────────────────────────────────────
    elif action == "set_metadata":
        metadata  = req.get("metadata", {})
        meta_path = os.path.join(SYNC_FOLDER, "UnrealMetadata.json")
        existing = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                existing = json.load(f)
        existing.update(metadata)
        with open(meta_path, "w") as f:
            json.dump(existing, f, indent=2)
        return {"status": "ok", "message": "Metadata saved"}

    # ── Asset list (read from sync folder) ────────────────────────────────────
    elif action == "get_asset_hierarchy":
        result = unreal_remote("/remote/assets", {})
        return result

    # ── Take Screenshot ───────────────────────────────────────────────────────
    elif action == "take_screenshot":
        import time
        import base64
        import glob
        import shutil
        shot_path = os.path.join(SYNC_FOLDER, "ue_screenshot.png")
        if os.path.exists(shot_path):
            try:
                os.remove(shot_path)
            except Exception:
                pass

        # Disable background throttling and trigger HighResShot console command
        ue_script = """import unreal
unreal.SystemLibrary.execute_console_command(None, "t.IdleWhenNotForeground 0")
unreal.SystemLibrary.execute_console_command(None, "HighResShot 1280x720")
"""
        temp_file = os.path.join(SYNC_FOLDER, "temp_screenshot.py")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(ue_script)
        except Exception as e:
            return {"status": "error", "message": f"Failed to write temp screenshot script: {str(e)}"}

        project_screenshots_dir = r"C:\Users\sassy\OneDrive\Documents\Unreal Projects\MyProject\Saved\Screenshots"
        
        # Record existing files before triggering screenshot
        existing_files = set()
        if os.path.exists(project_screenshots_dir):
            existing_files = set(glob.glob(os.path.join(project_screenshots_dir, "**", "*.png"), recursive=True))

        temp_file_ue = temp_file.replace("\\", "/")
        unreal_remote("/remote/object/call", {
            "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
            "functionName": "ExecuteConsoleCommand",
            "parameters": {
                "WorldContextObject": None,
                "Command": f'py "{temp_file_ue}"'
            }
        })

        # Poll for any new file appearing in project_screenshots_dir (up to 15 seconds)
        found_file = None
        for _ in range(150):
            if os.path.exists(project_screenshots_dir):
                current_files = set(glob.glob(os.path.join(project_screenshots_dir, "**", "*.png"), recursive=True))
                new_files = current_files - existing_files
                if new_files:
                    found_file = max(list(new_files), key=os.path.getmtime)
                    break
                elif current_files and not existing_files:
                    found_file = max(list(current_files), key=os.path.getmtime)
                    break
            time.sleep(0.1)

        if not found_file:
            return {"status": "error", "message": "Screenshot file was not generated by Unreal."}

        try:
            shutil.copy(found_file, shot_path)
            os.remove(found_file)
        except Exception as e:
            return {"status": "error", "message": f"Failed to copy/cleanup screenshot: {str(e)}"}

        try:
            from PIL import Image
            import io
            
            with Image.open(shot_path) as img:
                img = img.convert("RGB")
                width, height = img.size
                max_dim = 1024
                if width > max_dim or height > max_dim:
                    ratio = max_dim / max(width, height)
                    new_w = int(width * ratio)
                    new_h = int(height * ratio)
                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=70)
                img_bytes = buffer.getvalue()
                
            img_data = base64.b64encode(img_bytes).decode("utf-8")
            
            try:
                if os.path.exists(shot_path): os.remove(shot_path)
            except Exception:
                pass
                
            return {"status": "ok", "image_data": img_data}
        except Exception as e:
            try:
                with open(shot_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                return {"status": "ok", "image_data": img_data}
            except Exception as ex:
                return {"status": "error", "message": f"Failed to read/encode screenshot: {str(ex)}"}

    # ── Batch Create Actors ───────────────────────────────────────────────────
    elif action == "batch_create_actors":
        actors = req.get("actors", [])
        actors_data_str = json.dumps(actors)
        ue_script = f"""import unreal, json
actors_data = json.loads('''{actors_data_str}''')
shape_map = {{
    "Cube": "/Engine/BasicShapes/Cube.Cube",
    "Sphere": "/Engine/BasicShapes/Sphere.Sphere",
    "Cylinder": "/Engine/BasicShapes/Cylinder.Cylinder",
    "Cone": "/Engine/BasicShapes/Cone.Cone",
    "Plane": "/Engine/BasicShapes/Plane.Plane",
}}
loaded_meshes = {{}}
spawned_count = 0

for item in actors_data:
    shape = item.get("shape", "Cube").capitalize()
    name = item.get("name", f"Actor_{{spawned_count}}")
    loc = item.get("location", {{"x": 0, "y": 0, "z": 0}})
    scl = item.get("scale", {{"x": 1, "y": 1, "z": 1}})
    rot = item.get("rotation", {{"pitch": 0, "yaw": 0, "roll": 0}})
    
    mesh_path = shape_map.get(shape, shape_map["Cube"])
    if mesh_path not in loaded_meshes:
        loaded_meshes[mesh_path] = unreal.EditorAssetLibrary.load_asset(mesh_path)
    
    mesh_obj = loaded_meshes[mesh_path]
    if mesh_obj:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_object(
            mesh_obj,
            unreal.Vector(loc.get("x", 0), loc.get("y", 0), loc.get("z", 0))
        )
        if actor:
            actor.set_actor_label(name)
            actor.set_actor_scale3d(unreal.Vector(scl.get("x", 1), scl.get("y", 1), scl.get("z", 1)))
            actor.set_actor_rotation(unreal.Rotator(rot.get("pitch", 0), rot.get("yaw", 0), rot.get("roll", 0)), False)
            spawned_count += 1

unreal.log(f"batch_create_actors: Spawned {{spawned_count}} actor(s)")
"""
        return _exec_ue_script(ue_script, "batch_create_actors")

    # ── Spawn Blockout Primitive ──────────────────────────────────────────────
    elif action == "spawn_blockout_primitive":
        shape = req.get("shape", "Cube").capitalize()
        name  = req.get("name", "BlockoutActor")
        loc   = req.get("location", {"x": 0, "y": 0, "z": 0})
        scl   = req.get("scale", {"x": 1, "y": 1, "z": 1})

        # Map shape names to Unreal default static mesh paths
        shape_map = {
            "Cube":     "/Engine/BasicShapes/Cube.Cube",
            "Sphere":   "/Engine/BasicShapes/Sphere.Sphere",
            "Cylinder": "/Engine/BasicShapes/Cylinder.Cylinder",
            "Cone":     "/Engine/BasicShapes/Cone.Cone",
            "Plane":    "/Engine/BasicShapes/Plane.Plane",
        }
        mesh_path = shape_map.get(shape, shape_map["Cube"])

        # Write a temp Python script for Unreal to execute
        ue_script = f"""import unreal
astatic = unreal.EditorAssetLibrary.load_asset("{mesh_path}")
if astatic:
    actor = unreal.EditorLevelLibrary.spawn_actor_from_object(astatic, unreal.Vector({loc.get('x',0)}, {loc.get('y',0)}, {loc.get('z',0)}))
    if actor:
        actor.set_actor_label("{name}")
        actor.set_actor_scale3d(unreal.Vector({scl.get('x',1)}, {scl.get('y',1)}, {scl.get('z',1)}))
        unreal.log("Spawned blockout: {name}")
else:
    unreal.log_warning("Could not load mesh: {mesh_path}")
"""
        temp_file = os.path.join(SYNC_FOLDER, "temp_blockout.py")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(ue_script)

        temp_file_ue = temp_file.replace("\\", "/")
        result = unreal_remote("/remote/object/call", {
            "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
            "functionName": "ExecuteConsoleCommand",
            "parameters": {
                "WorldContextObject": None,
                "Command": f'py "{temp_file_ue}"'
            }
        })
        result["spawned"] = name
        result["shape"] = shape
        return result

    # ── Import FBX ────────────────────────────────────────────────────────────
    elif action == "import_fbx":
        filename    = req.get("filename", "")
        destination = req.get("destination", "/Game/BlenderSync/")
        fbx_path    = os.path.join(SYNC_FOLDER, filename)

        if not os.path.exists(fbx_path):
            return {"status": "error", "message": f"FBX file not found: {fbx_path}"}

        fbx_path_ue = fbx_path.replace("\\", "/")
        ue_script = f"""import unreal
task = unreal.AssetImportTask()
task.filename = "{fbx_path_ue}"
task.destination_path = "{destination}"
task.automated = True
task.replace_existing = True
task.save = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
unreal.log("Imported FBX: {filename} -> {destination}")
"""
        temp_file = os.path.join(SYNC_FOLDER, "temp_import.py")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(ue_script)

        temp_file_ue = temp_file.replace("\\", "/")
        result = unreal_remote("/remote/object/call", {
            "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
            "functionName": "ExecuteConsoleCommand",
            "parameters": {
                "WorldContextObject": None,
                "Command": f'py "{temp_file_ue}"'
            }
        })
        result["imported"] = filename
        result["destination"] = destination
        return result

    # ── Import Animation ──────────────────────────────────────────────────────
    elif action == "import_animation_to_unreal":
        filepath = req.get("filepath")
        destination_path = req.get("destination_path", "/Game/Animations")
        skeleton_path = req.get("skeleton_path")

        if not filepath or not skeleton_path:
            return {"status": "error", "message": "filepath and skeleton_path required"}
            
        filepath_ue = filepath.replace("\\", "/")
        ue_script = f"""import unreal
task = unreal.AssetImportTask()
task.filename = "{filepath_ue}"
task.destination_path = "{destination_path}"
task.automated = True
task.save = True
task.replace_existing = True

options = unreal.FbxImportUI()
options.import_animations = True
options.import_as_skeletal = True
options.import_mesh = False
options.skeleton = unreal.EditorAssetLibrary.load_asset("{skeleton_path}")

task.options = options
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
unreal.log("Imported animation: {filepath_ue} -> {destination_path}")
"""
        return _exec_ue_script(ue_script, "import_animation_to_unreal")

    # ── Create Landscape ──────────────────────────────────────────────────────
    elif action == "create_landscape":
        loc = req.get("location", {"x": 0, "y": 0, "z": 0})
        scl = req.get("scale", {"x": 100, "y": 100, "z": 100})
        section_size = req.get("section_size", 63)
        sections_per = req.get("sections_per_component", 1)
        num_x = req.get("num_components_x", 8)
        num_y = req.get("num_components_y", 8)
        material = req.get("material", "")

        mat_line = ""
        if material:
            mat_line = f"""
mat = unreal.EditorAssetLibrary.load_asset("{material}")
if mat and landscape:
    landscape.set_editor_property("landscape_material", mat)
    unreal.log("Set landscape material: {material}")
"""

        ue_script = f"""import unreal
import struct

# Calculate total resolution
quads_per_section = {section_size}
sections = {sections_per}
num_comp_x = {num_x}
num_comp_y = {num_y}
size_x = quads_per_section * sections * num_comp_x + 1
size_y = quads_per_section * sections * num_comp_y + 1

# Create flat heightmap data (mid-height = 32768 for 16-bit)
height_data = [32768] * (size_x * size_y)

# Create the landscape proxy
world = unreal.EditorLevelLibrary.get_editor_world()
landscape = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.LandscapeStreamingProxy if False else unreal.Landscape,
    unreal.Vector({loc.get('x',0)}, {loc.get('y',0)}, {loc.get('z',0)})
)
if landscape:
    landscape.set_actor_scale3d(unreal.Vector({scl.get('x',100)}, {scl.get('y',100)}, {scl.get('z',100)}))
    unreal.log(f"Created Landscape at {{landscape.get_actor_location()}} with resolution {{size_x}}x{{size_y}}")
else:
    unreal.log_warning("Failed to create landscape via spawn. Use Edit > Landscape Mode in editor for full control.")
{mat_line}
"""
        return _exec_ue_script(ue_script, "create_landscape")

    # ── Import Heightmap ─────────────────────────────────────────────────────
    elif action == "import_heightmap":
        filename = req.get("filename", "")
        landscape_name = req.get("landscape_name", "Landscape")
        hm_path = os.path.join(SYNC_FOLDER, filename).replace("\\", "/")

        if not os.path.exists(os.path.join(SYNC_FOLDER, filename)):
            return {"status": "error", "message": f"Heightmap file not found: {hm_path}"}

        ue_script = f"""import unreal

# Find landscape
actors = unreal.EditorLevelLibrary.get_all_level_actors()
landscape = None
for a in actors:
    if a.get_actor_label() == "{landscape_name}" and isinstance(a, unreal.Landscape):
        landscape = a
        break

if not landscape:
    unreal.log_warning("Landscape '{landscape_name}' not found.")
else:
    # Use the LandscapeEditorLibrary or console command to import
    unreal.SystemLibrary.execute_console_command(
        None,
        'Landscape.ImportHeightmap filename="{hm_path}"'
    )
    unreal.log("Heightmap import command sent for: {filename}")
"""
        return _exec_ue_script(ue_script, "import_heightmap")

    # ── Export Heightmap ──────────────────────────────────────────────────────
    elif action == "export_heightmap":
        landscape_name = req.get("landscape_name", "Landscape")
        filename = req.get("filename", "landscape_heightmap.png")
        out_path = os.path.join(SYNC_FOLDER, filename).replace("\\", "/")

        ue_script = f"""import unreal

actors = unreal.EditorLevelLibrary.get_all_level_actors()
landscape = None
for a in actors:
    if a.get_actor_label() == "{landscape_name}" and isinstance(a, unreal.Landscape):
        landscape = a
        break

if not landscape:
    unreal.log_warning("Landscape '{landscape_name}' not found.")
else:
    unreal.SystemLibrary.execute_console_command(
        None,
        'Landscape.ExportHeightmap filename="{out_path}"'
    )
    unreal.log("Heightmap export command sent -> {out_path}")
"""
        return _exec_ue_script(ue_script, "export_heightmap")

    # ── Sculpt Landscape ─────────────────────────────────────────────────────
    elif action == "sculpt_landscape":
        points = req.get("points", [])
        landscape_name = req.get("landscape_name", "Landscape")

        # Build Python list of sculpt ops
        points_str = json.dumps(points)
        ue_script = f"""import unreal
import json

points = json.loads('{points_str}')
actors = unreal.EditorLevelLibrary.get_all_level_actors()
landscape = None
for a in actors:
    if a.get_actor_label() == "{landscape_name}" and isinstance(a, unreal.Landscape):
        landscape = a
        break

if not landscape:
    unreal.log_warning("Landscape '{landscape_name}' not found.")
else:
    subsystem = unreal.get_editor_subsystem(unreal.LandscapeEditorSubsystem) if hasattr(unreal, 'LandscapeEditorSubsystem') else None
    if subsystem:
        for pt in points:
            loc = unreal.Vector(pt.get("x", 0), pt.get("y", 0), 0)
            subsystem.sculpt(loc, pt.get("radius", 1000), pt.get("strength", 0.5))
        unreal.log(f"Sculpted {{len(points)}} points on landscape.")
    else:
        # Fallback: modify via heightmap data directly
        unreal.log_warning("LandscapeEditorSubsystem not available. Use execute_unreal_python with custom heightmap manipulation for advanced sculpting.")
        unreal.log(f"Requested sculpt at {{len(points)}} points - manual approach required in this UE version.")
"""
        return _exec_ue_script(ue_script, "sculpt_landscape")

    # ── Paint Landscape Layer ────────────────────────────────────────────────
    elif action == "paint_landscape_layer":
        layer_name = req.get("layer_name", "")
        points = req.get("points", [])
        landscape_name = req.get("landscape_name", "Landscape")
        points_str = json.dumps(points)

        ue_script = f"""import unreal
import json

points = json.loads('{points_str}')
actors = unreal.EditorLevelLibrary.get_all_level_actors()
landscape = None
for a in actors:
    if a.get_actor_label() == "{landscape_name}" and isinstance(a, unreal.Landscape):
        landscape = a
        break

if not landscape:
    unreal.log_warning("Landscape '{landscape_name}' not found.")
else:
    subsystem = unreal.get_editor_subsystem(unreal.LandscapeEditorSubsystem) if hasattr(unreal, 'LandscapeEditorSubsystem') else None
    if subsystem:
        for pt in points:
            loc = unreal.Vector(pt.get("x", 0), pt.get("y", 0), 0)
            subsystem.paint_layer("{layer_name}", loc, pt.get("radius", 1000), pt.get("strength", 1.0))
        unreal.log(f"Painted {{len(points)}} points with layer '{layer_name}'.")
    else:
        unreal.log_warning("LandscapeEditorSubsystem not available for painting in this UE version.")
"""
        return _exec_ue_script(ue_script, "paint_landscape_layer")

    # ── Set Landscape Material ───────────────────────────────────────────────
    elif action == "set_landscape_material":
        material_path = req.get("material_path", "")
        landscape_name = req.get("landscape_name", "Landscape")

        ue_script = f"""import unreal

actors = unreal.EditorLevelLibrary.get_all_level_actors()
landscape = None
for a in actors:
    if a.get_actor_label() == "{landscape_name}" and isinstance(a, unreal.Landscape):
        landscape = a
        break

if not landscape:
    unreal.log_warning("Landscape '{landscape_name}' not found.")
else:
    mat = unreal.EditorAssetLibrary.load_asset("{material_path}")
    if mat:
        landscape.set_editor_property("landscape_material", mat)
        unreal.log("Landscape material set to: {material_path}")
    else:
        unreal.log_warning("Material not found: {material_path}")
"""
        return _exec_ue_script(ue_script, "set_landscape_material")

    # ── Get Landscape Info ───────────────────────────────────────────────────
    elif action == "get_landscape_info":
        landscape_name = req.get("landscape_name", "Landscape")

        ue_script = f"""import unreal
import json

actors = unreal.EditorLevelLibrary.get_all_level_actors()
landscape = None
for a in actors:
    if a.get_actor_label() == "{landscape_name}" and isinstance(a, unreal.Landscape):
        landscape = a
        break

if not landscape:
    print(json.dumps({{"status": "error", "message": "Landscape not found"}}))
else:
    loc = landscape.get_actor_location()
    scl = landscape.get_actor_scale3d()
    bounds_origin, bounds_extent = landscape.get_actor_bounds(False)
    
    mat = landscape.get_editor_property("landscape_material")
    mat_name = mat.get_path_name() if mat else "None"
    
    info = {{
        "name": landscape.get_actor_label(),
        "location": {{"x": loc.x, "y": loc.y, "z": loc.z}},
        "scale": {{"x": scl.x, "y": scl.y, "z": scl.z}},
        "bounds_origin": {{"x": bounds_origin.x, "y": bounds_origin.y, "z": bounds_origin.z}},
        "bounds_extent": {{"x": bounds_extent.x, "y": bounds_extent.y, "z": bounds_extent.z}},
        "material": mat_name,
    }}
    print(json.dumps(info))
"""
        return _exec_ue_script(ue_script, "get_landscape_info")

    # ── Add Foliage ──────────────────────────────────────────────────────────
    elif action == "add_foliage":
        foliage_type = req.get("foliage_type", "")
        instances = req.get("instances", [])
        align = req.get("align_to_surface", True)
        instances_str = json.dumps(instances)

        ue_script = f"""import unreal
import json

instances = json.loads('{instances_str}')
mesh = unreal.EditorAssetLibrary.load_asset("{foliage_type}")
if not mesh:
    unreal.log_warning("Foliage asset not found: {foliage_type}")
else:
    # Get or create the Instanced Foliage Actor
    world = unreal.EditorLevelLibrary.get_editor_world()
    
    for inst in instances:
        loc = unreal.Vector(inst.get("x", 0), inst.get("y", 0), inst.get("z", 0))
        rot = unreal.Rotator(inst.get("pitch", 0), inst.get("yaw", 0), inst.get("roll", 0))
        scale_val = inst.get("scale", 1.0)
        
        # Spawn as a static mesh actor (simplest cross-version approach)
        actor = unreal.EditorLevelLibrary.spawn_actor_from_object(mesh, loc)
        if actor:
            actor.set_actor_rotation(rot, False)
            actor.set_actor_scale3d(unreal.Vector(scale_val, scale_val, scale_val))
            actor.set_folder_path("Foliage")
    
    unreal.log(f"Placed {{len(instances)}} foliage instances of {foliage_type}")
"""
        return _exec_ue_script(ue_script, "add_foliage")

    # ── Remove Foliage ───────────────────────────────────────────────────────
    elif action == "remove_foliage":
        x = req.get("x", 0)
        y = req.get("y", 0)
        z = req.get("z", 0)
        radius = req.get("radius", 500)
        foliage_filter = req.get("foliage_type", "")

        ue_script = f"""import unreal

center = unreal.Vector({x}, {y}, {z})
radius = {radius}
removed = 0

actors = unreal.EditorLevelLibrary.get_all_level_actors()
for actor in actors:
    if actor.get_folder_path() == "Foliage" or "Foliage" in actor.get_actor_label():
        dist = (actor.get_actor_location() - center).length()
        if dist <= radius:
            unreal.EditorLevelLibrary.destroy_actor(actor)
            removed += 1

unreal.log(f"Removed {{removed}} foliage actors within radius {radius}")
"""
        return _exec_ue_script(ue_script, "remove_foliage")

    # ── Mesh Boolean ─────────────────────────────────────────────────────────
    elif action == "mesh_boolean":
        target = req.get("target_actor", "")
        tool = req.get("tool_actor", "")
        operation = req.get("operation", "subtract")

        ue_script = f"""import unreal

actors = unreal.EditorLevelLibrary.get_all_level_actors()
target_actor = None
tool_actor = None
for a in actors:
    if a.get_actor_label() == "{target}":
        target_actor = a
    if a.get_actor_label() == "{tool}":
        tool_actor = a

if not target_actor:
    unreal.log_warning("Target actor '{target}' not found.")
elif not tool_actor:
    unreal.log_warning("Tool actor '{tool}' not found.")
else:
    # Use Geometry Script if available (UE 5.x)
    try:
        geo_lib = unreal.GeometryScriptLibrary
        unreal.log("GeometryScript available - boolean operations supported in Modeling Mode.")
    except:
        pass
    
    # Fallback: select both actors and use editor command
    unreal.EditorLevelLibrary.set_selected_level_actors([target_actor, tool_actor])
    op_map = {{"subtract": "MeshBooleanSubtract", "union": "MeshBooleanUnion", "intersect": "MeshBooleanIntersect"}}
    cmd = op_map.get("{operation}", "MeshBooleanSubtract")
    unreal.SystemLibrary.execute_console_command(None, cmd)
    unreal.log(f"Boolean {{'{operation}'}} executed: {{'{target}'}} with {{'{tool}'}}")
"""
        return _exec_ue_script(ue_script, "mesh_boolean")

    # ── Generate Mesh from Spline ────────────────────────────────────────────
    elif action == "generate_mesh_from_spline":
        name = req.get("name", "SplineMesh")
        spline_points = req.get("spline_points", [])
        width = req.get("width", 200)
        closed = req.get("closed", False)
        points_str = json.dumps(spline_points)

        ue_script = f"""import unreal
import json

points = json.loads('{points_str}')

# Create a SplineComponent-based actor
actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.Actor,
    unreal.Vector(0, 0, 0)
)
if actor:
    actor.set_actor_label("{name}")
    
    # Add a spline component
    spline = actor.add_component_by_class(unreal.SplineComponent, False, unreal.Transform(), False)
    if spline:
        spline.clear_spline_points()
        for i, pt in enumerate(points):
            spline.add_spline_point(
                unreal.Vector(pt.get("x", 0), pt.get("y", 0), pt.get("z", 0)),
                unreal.SplineCoordinateSpace.WORLD,
                True
            )
        spline.set_closed_loop({str(closed)})
        spline.update_spline()
        unreal.log(f"Created spline '{{actor.get_actor_label()}}' with {{len(points)}} points, width={width}")
    
    actor.set_folder_path("GeneratedMeshes")
"""
        return _exec_ue_script(ue_script, "generate_mesh_from_spline")

    # ── PCG Component Creation ────────────────────────────────────────────────
    elif action == "create_pcg_component":
        actor_name = req.get("actor_name", "")
        graph_path = req.get("graph_path", "")
        loc = req.get("location", {"x": 0, "y": 0, "z": 0})
        scl = req.get("scale", {"x": 1, "y": 1, "z": 1})

        x = loc.get("x", 0)
        y = loc.get("y", 0)
        z = loc.get("z", 0)
        sx = scl.get("x", 1)
        sy = scl.get("y", 1)
        sz = scl.get("z", 1)

        ue_script = f"""import unreal
graph_path = "{graph_path}"
actor_name = "{actor_name}"
pcg_graph = unreal.EditorAssetLibrary.load_asset(graph_path) if graph_path else None

actor = None
if actor_name:
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    for a in actors:
        if a.get_actor_label() == actor_name:
            actor = a
            break

if not actor:
    label = actor_name if actor_name else "PCGActor"
    loc = unreal.Vector({x}, {y}, {z})
    scl = unreal.Vector({sx}, {sy}, {sz})
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.Actor, loc)
    if actor:
        actor.set_actor_label(label)
        actor.set_actor_scale3d(scl)

if actor and pcg_graph:
    pcg_comp = actor.find_component_by_class(unreal.PCGComponent)
    if not pcg_comp:
        pcg_comp = actor.add_component_by_class(unreal.PCGComponent, False, unreal.Transform(), False)
    if pcg_comp:
        try:
            pcg_comp.set_graph(pcg_graph)
        except:
            try:
                pcg_comp.set_editor_property("graph", pcg_graph)
            except Exception as e:
                unreal.log_warning(f"Failed to set graph: {{e}}")
        unreal.log(f"Configured PCG component with graph {{graph_path}} on {{actor.get_actor_label()}}")
"""
        return _exec_ue_script(ue_script, "create_pcg_component")

    # ── PCG Generate ──────────────────────────────────────────────────────────
    elif action == "pcg_generate":
        actor_name = req.get("actor_name", "")
        ue_script = f"""import unreal
actor_name = "{actor_name}"
actors = unreal.EditorLevelLibrary.get_all_level_actors()
for a in actors:
    if a.get_actor_label() == actor_name:
        pcg_comp = a.find_component_by_class(unreal.PCGComponent)
        if pcg_comp:
            pcg_comp.generate()
            unreal.log(f"Generated PCG on: {{actor_name}}")
        break
"""
        return _exec_ue_script(ue_script, "pcg_generate")

    # ── PCG Cleanup ───────────────────────────────────────────────────────────
    elif action == "pcg_cleanup":
        actor_name = req.get("actor_name", "")
        ue_script = f"""import unreal
actor_name = "{actor_name}"
actors = unreal.EditorLevelLibrary.get_all_level_actors()
for a in actors:
    if a.get_actor_label() == actor_name:
        pcg_comp = a.find_component_by_class(unreal.PCGComponent)
        if pcg_comp:
            pcg_comp.cleanup()
            unreal.log(f"Cleaned up PCG on: {{actor_name}}")
        break
"""
        return _exec_ue_script(ue_script, "pcg_cleanup")

    # ── PCG Set Parameter ─────────────────────────────────────────────────────
    elif action == "pcg_set_parameter":
        actor_name = req.get("actor_name", "")
        param_name = req.get("parameter_name", "")
        val = req.get("value", None)
        val_type = req.get("value_type", "")

        val_json = json.dumps(val)

        ue_script = f"""import unreal, json
actor_name = "{actor_name}"
param_name = "{param_name}"
val_json = json.loads('''{val_json}''')
val_type = "{val_type}".lower()

actors = unreal.EditorLevelLibrary.get_all_level_actors()
pcg_comp = None
for a in actors:
    if a.get_actor_label() == actor_name:
        pcg_comp = a.find_component_by_class(unreal.PCGComponent)
        break

if pcg_comp:
    graph_instance = pcg_comp.get_editor_property("graph_instance")
    if not graph_instance:
        graph_instance = pcg_comp.get_editor_property("graph")

    if graph_instance:
        try:
            helpers = unreal.PCGGraphParametersHelpers
            # Auto-detect if type not explicitly specified
            if val_type == "float" or (not val_type and isinstance(val_json, float)):
                helpers.set_float_parameter(graph_instance, param_name, float(val_json))
            elif val_type == "int" or (not val_type and isinstance(val_json, int) and not isinstance(val_json, bool)):
                helpers.set_int_parameter(graph_instance, param_name, int(val_json))
            elif val_type == "bool" or (not val_type and isinstance(val_json, bool)):
                helpers.set_bool_parameter(graph_instance, param_name, bool(val_json))
            elif val_type == "string" or (not val_type and isinstance(val_json, str)):
                helpers.set_string_parameter(graph_instance, param_name, str(val_json))
            elif val_type == "vector" or (not val_type and (isinstance(val_json, dict) or isinstance(val_json, list))):
                if isinstance(val_json, dict):
                    v = unreal.Vector(val_json.get("x", 0), val_json.get("y", 0), val_json.get("z", 0))
                else:
                    v = unreal.Vector(val_json[0], val_json[1], val_json[2])
                helpers.set_vector_parameter(graph_instance, param_name, v)
            elif val_type == "rotator":
                if isinstance(val_json, dict):
                    r = unreal.Rotator(val_json.get("pitch", 0), val_json.get("yaw", 0), val_json.get("roll", 0))
                else:
                    r = unreal.Rotator(val_json[0], val_json[1], val_json[2])
                helpers.set_rotator_parameter(graph_instance, param_name, r)
            else:
                helpers.set_string_parameter(graph_instance, param_name, str(val_json))
            unreal.log(f"Set PCG parameter {{param_name}} to {{val_json}} on {{actor_name}}")
        except Exception as e:
            unreal.log_warning(f"Error setting PCG parameter {{param_name}}: {{e}}")
"""
        return _exec_ue_script(ue_script, "pcg_set_parameter")

    # ── PCG Get Parameters ────────────────────────────────────────────────────
    elif action == "pcg_get_parameters":
        actor_name = req.get("actor_name", "")
        ue_script = f"""import unreal, json
actor_name = "{actor_name}"
actors = unreal.EditorLevelLibrary.get_all_level_actors()
info = {{"status": "error", "message": "PCG Component not found"}}
for a in actors:
    if a.get_actor_label() == actor_name:
        pcg_comp = a.find_component_by_class(unreal.PCGComponent)
        if pcg_comp:
            graph_instance = pcg_comp.get_editor_property("graph_instance")
            graph = pcg_comp.get_editor_property("graph")
            info = {{
                "status": "ok",
                "actor": actor_name,
                "has_graph": graph is not None,
                "graph_path": graph.get_path_name() if graph else "None",
                "has_graph_instance": graph_instance is not None
            }}
        break

out_path = "{SYNC_FOLDER.replace('\\\\', '/')}/pcg_info.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(info, f)
"""
        _exec_ue_script(ue_script, "pcg_get_parameters")
        info_file = os.path.join(SYNC_FOLDER, "pcg_info.json")
        if os.path.exists(info_file):
            try:
                with open(info_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"status": "ok"}

    # ── Precision Align Actors ────────────────────────────────────────────────
    elif action == "align_actors":
        actor_a_name = req.get("actor_a_name", "")
        actor_b_name = req.get("actor_b_name", "")
        axis = req.get("axis", "+X").upper()
        offset = req.get("offset", 0.0)

        ue_script = f"""import unreal
actor_a_name = "{actor_a_name}"
actor_b_name = "{actor_b_name}"
axis = "{axis}"
offset = {offset}

actors = unreal.EditorLevelLibrary.get_all_level_actors()
actor_a, actor_b = None, None
for a in actors:
    if a.get_actor_label() == actor_a_name:
        actor_a = a
    if a.get_actor_label() == actor_b_name:
        actor_b = a

if actor_a and actor_b:
    origin_a, extent_a = actor_a.get_actor_bounds(False)
    origin_b, extent_b = actor_b.get_actor_bounds(False)
    
    loc_b = actor_b.get_actor_location()
    new_loc = unreal.Vector(loc_b.x, loc_b.y, loc_b.z)
    
    if axis == "+X":
        new_loc.x = origin_a.x + extent_a.x + extent_b.x + offset
    elif axis == "-X":
        new_loc.x = origin_a.x - extent_a.x - extent_b.x - offset
    elif axis == "+Y":
        new_loc.y = origin_a.y + extent_a.y + extent_b.y + offset
    elif axis == "-Y":
        new_loc.y = origin_a.y - extent_a.y - extent_b.y - offset
    elif axis == "+Z":
        new_loc.z = origin_a.z + extent_a.z + extent_b.z + offset
    elif axis == "-Z":
        new_loc.z = origin_a.z - extent_a.z - extent_b.z - offset
        
    actor_b.set_actor_location(new_loc, False, True)
    unreal.log(f"Aligned {{actor_b_name}} with {{actor_a_name}} along {{axis}} (new_loc: {{new_loc}})")
"""
        return _exec_ue_script(ue_script, "align_actors")

    # ── Get Actor Dimensions ──────────────────────────────────────────────────
    elif action == "get_actor_dimensions":
        actor_name = req.get("actor_name", "")

        ue_script = f"""import unreal, json

actor_name = "{actor_name}"
actors = unreal.EditorLevelLibrary.get_all_level_actors()
result = {{"status": "error", "message": f"Actor '{{actor_name}}' not found"}}

for a in actors:
    if a.get_actor_label() == actor_name:
        origin, extent = a.get_actor_bounds(False)
        loc = a.get_actor_location()
        scl = a.get_actor_scale3d()
        result = {{
            "status": "ok",
            "actor": actor_name,
            "location": {{"x": loc.x, "y": loc.y, "z": loc.z}},
            "scale": {{"x": scl.x, "y": scl.y, "z": scl.z}},
            "bounds_origin": {{"x": origin.x, "y": origin.y, "z": origin.z}},
            "bounds_extent": {{"x": extent.x, "y": extent.y, "z": extent.z}},
            "size_x_cm": extent.x * 2,
            "size_y_cm": extent.y * 2,
            "size_z_cm": extent.z * 2,
            "min_x": origin.x - extent.x,
            "max_x": origin.x + extent.x,
            "min_y": origin.y - extent.y,
            "max_y": origin.y + extent.y,
            "min_z": origin.z - extent.z,
            "max_z": origin.z + extent.z,
        }}
        break

out_path = "{SYNC_FOLDER.replace('\\\\', '/')}/actor_dimensions.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f)
"""
        _exec_ue_script(ue_script, "get_actor_dimensions")
        dim_file = os.path.join(SYNC_FOLDER, "actor_dimensions.json")
        if os.path.exists(dim_file):
            try:
                with open(dim_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"status": "error", "message": "Failed to read dimensions"}

    # ── Snap to Grid ──────────────────────────────────────────────────────────
    elif action == "snap_to_grid":
        actor_name = req.get("actor_name", "")
        grid_size = req.get("grid_size", 100.0)

        ue_script = f"""import unreal

actor_name = "{actor_name}"
grid = {grid_size}

import math

actors = unreal.EditorLevelLibrary.get_all_level_actors()
for a in actors:
    if a.get_actor_label() == actor_name:
        loc = a.get_actor_location()
        snapped = unreal.Vector(
            round(loc.x / grid) * grid,
            round(loc.y / grid) * grid,
            round(loc.z / grid) * grid
        )
        a.set_actor_location(snapped, False, True)
        unreal.log(f"Snapped {{actor_name}} to grid {{grid}}: {{snapped}}")
        break
"""
        return _exec_ue_script(ue_script, "snap_to_grid")

    # ── Verify Actor Alignment ────────────────────────────────────────────────
    elif action == "verify_actor_alignment":
        actor_a_name = req.get("actor_a_name", "")
        actor_b_name = req.get("actor_b_name", "")
        axis = req.get("axis", "X").upper().replace("+", "").replace("-", "")

        ue_script = f"""import unreal, json

actor_a_name = "{actor_a_name}"
actor_b_name = "{actor_b_name}"
axis = "{axis}"

actors = unreal.EditorLevelLibrary.get_all_level_actors()
actor_a, actor_b = None, None
for a in actors:
    if a.get_actor_label() == actor_a_name:
        actor_a = a
    if a.get_actor_label() == actor_b_name:
        actor_b = a

result = {{"status": "error", "message": "One or both actors not found"}}

if actor_a and actor_b:
    origin_a, extent_a = actor_a.get_actor_bounds(False)
    origin_b, extent_b = actor_b.get_actor_bounds(False)

    if axis == "X":
        a_max = origin_a.x + extent_a.x
        b_min = origin_b.x - extent_b.x
        a_min = origin_a.x - extent_a.x
        b_max = origin_b.x + extent_b.x
    elif axis == "Y":
        a_max = origin_a.y + extent_a.y
        b_min = origin_b.y - extent_b.y
        a_min = origin_a.y - extent_a.y
        b_max = origin_b.y + extent_b.y
    else:  # Z
        a_max = origin_a.z + extent_a.z
        b_min = origin_b.z - extent_b.z
        a_min = origin_a.z - extent_a.z
        b_max = origin_b.z + extent_b.z

    # gap > 0 means apart, < 0 means overlap, == 0 means perfect touch
    gap_ab = b_min - a_max   # B's near face minus A's far face
    gap_ba = a_min - b_max   # A's near face minus B's far face

    if gap_ab >= -0.1 and gap_ab <= 0.1:
        status_str = "TOUCHING_PERFECTLY"
    elif gap_ab > 0.1:
        status_str = "GAP"
    elif gap_ba >= -0.1 and gap_ba <= 0.1:
        status_str = "TOUCHING_PERFECTLY_REVERSED"
    elif gap_ba > 0.1:
        status_str = "GAP_REVERSED"
    else:
        status_str = "OVERLAPPING"

    result = {{
        "status": "ok",
        "axis": axis,
        "actor_a": actor_a_name,
        "actor_b": actor_b_name,
        "alignment_status": status_str,
        "gap_a_to_b_cm": round(gap_ab, 4),
        "gap_b_to_a_cm": round(gap_ba, 4),
        "a_max_{axis.lower()}": round(a_max, 4),
        "b_min_{axis.lower()}": round(b_min, 4),
        "is_correct": status_str in ("TOUCHING_PERFECTLY", "TOUCHING_PERFECTLY_REVERSED")
    }}

out_path = "{SYNC_FOLDER.replace('\\\\', '/')}/alignment_check.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f)
"""
        _exec_ue_script(ue_script, "verify_actor_alignment")
        check_file = os.path.join(SYNC_FOLDER, "alignment_check.json")
        if os.path.exists(check_file):
            try:
                with open(check_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"status": "error", "message": "Failed to read alignment check"}

    # ── Blueprint Tools ───────────────────────────────────────────────────────
    elif action == "create_blueprint_class":
        class_name = req.get("class_name", "")
        parent_class = req.get("parent_class", "Actor")
        save_path = req.get("save_path", "/Game/Blueprints")
        ue_script = f"""import unreal
factory = unreal.BlueprintFactory()
factory.set_editor_property('parent_class', unreal.load_class(None, f'/Script/Engine.{parent_class}'))
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
bp = asset_tools.create_asset('{class_name}', '{save_path}', unreal.Blueprint, factory)
unreal.log(f'Created Blueprint: {{bp.get_path_name() if bp else "FAILED"}}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "compile_blueprint":
        blueprint_path = req.get("blueprint_path", "")
        ue_script = f"""import unreal
bp = unreal.load_asset('{blueprint_path}')
if bp:
    unreal.KismetEditorUtilities.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset('{blueprint_path}')
    unreal.log('Compiled: {blueprint_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "add_blueprint_component":
        blueprint_path = req.get("blueprint_path", "")
        component_class = req.get("component_class", "")
        component_name = req.get("component_name", "")
        ue_script = f"""import unreal
bp = unreal.load_asset('{blueprint_path}')
comp_class = unreal.load_class(None, f'/Script/Engine.{component_class}')
if bp and comp_class:
    unreal.BlueprintEditorLibrary.add_component_to_blueprint(bp, comp_class, '{component_name}')
    unreal.KismetEditorUtilities.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset('{blueprint_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_blueprint_default_value":
        blueprint_path = req.get("blueprint_path", "")
        property_name = req.get("property_name", "")
        property_value = req.get("property_value", "")
        try:
            val = json.loads(property_value)
        except:
            val = property_value
        property_value_repr = repr(val)
        ue_script = f"""import unreal
bp = unreal.load_asset('{blueprint_path}')
if bp:
    cdo = unreal.get_default_object(bp.generated_class())
    try:
        prop_val = {property_value_repr}
        setattr(cdo, '{property_name}', prop_val)
        unreal.KismetEditorUtilities.compile_blueprint(bp)
        unreal.EditorAssetLibrary.save_asset('{blueprint_path}')
    except Exception as e:
        unreal.log_warning(f'set_blueprint_default_value: {{e}}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "reparent_blueprint":
        blueprint_path = req.get("blueprint_path", "")
        new_parent_class = req.get("new_parent_class", "")
        ue_script = f"""import unreal
bp = unreal.load_asset('{blueprint_path}')
new_parent = unreal.load_class(None, f'/Script/Engine.{new_parent_class}')
if bp and new_parent:
    unreal.BlueprintEditorLibrary.reparent_blueprint(bp, new_parent)
    unreal.KismetEditorUtilities.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset('{blueprint_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "get_blueprint_info":
        blueprint_path = req.get("blueprint_path", "")
        sync_folder_fwd = SYNC_FOLDER.replace(chr(92), '/')
        ue_script = f"""import unreal, json
bp = unreal.load_asset('{blueprint_path}')
result = {{'status': 'error', 'message': 'Blueprint not found'}}
if bp:
    parent = bp.generated_class().get_super_class().get_name() if bp.generated_class() else 'Unknown'
    result = {{
        'status': 'ok',
        'path': '{blueprint_path}',
        'parent_class': parent,
        'has_errors': bool(bp.status != unreal.BlueprintStatus.BS_UP_TO_DATE)
    }}
with open('{sync_folder_fwd}/bp_info.json', 'w') as f:
    json.dump(result, f)
"""
        _exec_ue_script(ue_script, action)
        res_file = os.path.join(SYNC_FOLDER, "bp_info.json")
        try:
            with open(res_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"status": "error", "message": "Failed to read result"}

    # ── Material Tools ────────────────────────────────────────────────────────
    elif action == "create_material_asset":
        material_name = req.get("material_name", "")
        save_path = req.get("save_path", "/Game/Materials")
        ue_script = f"""import unreal
factory = unreal.MaterialFactoryNew()
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mat = asset_tools.create_asset('{material_name}', '{save_path}', unreal.Material, factory)
if mat:
    unreal.EditorAssetLibrary.save_asset(mat.get_path_name())
    unreal.log(f'Created Material: {{mat.get_path_name()}}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "create_material_instance":
        instance_name = req.get("instance_name", "")
        parent_path = req.get("parent_path", "")
        save_path = req.get("save_path", "/Game/Materials")
        ue_script = f"""import unreal
parent = unreal.load_asset('{parent_path}')
if parent:
    factory = unreal.MaterialInstanceConstantFactoryNew()
    factory.set_editor_property('initial_parent', parent)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    mi = asset_tools.create_asset('{instance_name}', '{save_path}', unreal.MaterialInstanceConstant, factory)
    if mi:
        unreal.EditorAssetLibrary.save_asset(mi.get_path_name())
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_material_scalar_param":
        material_instance_path = req.get("material_instance_path", "")
        param_name = req.get("param_name", "")
        value = req.get("value", 0.0)
        ue_script = f"""import unreal
mi = unreal.load_asset('{material_instance_path}')
if mi:
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, '{param_name}', {value})
    unreal.EditorAssetLibrary.save_asset('{material_instance_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_material_vector_param":
        material_instance_path = req.get("material_instance_path", "")
        param_name = req.get("param_name", "")
        r = req.get("r", 0.0)
        g = req.get("g", 0.0)
        b = req.get("b", 0.0)
        a = req.get("a", 1.0)
        ue_script = f"""import unreal
mi = unreal.load_asset('{material_instance_path}')
if mi:
    color = unreal.LinearColor(r={r}, g={g}, b={b}, a={a})
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi, '{param_name}', color)
    unreal.EditorAssetLibrary.save_asset('{material_instance_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_material_texture_param":
        material_instance_path = req.get("material_instance_path", "")
        param_name = req.get("param_name", "")
        texture_path = req.get("texture_path", "")
        ue_script = f"""import unreal
mi = unreal.load_asset('{material_instance_path}')
tex = unreal.load_asset('{texture_path}')
if mi and tex:
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi, '{param_name}', tex)
    unreal.EditorAssetLibrary.save_asset('{material_instance_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_nanite_enabled":
        mesh_path = req.get("mesh_path", "")
        enabled_py = str(req.get("enabled", True))
        ue_script = f"""import unreal
mesh = unreal.load_asset('{mesh_path}')
if mesh:
    settings = unreal.MeshNaniteSettings()
    settings.enabled = {enabled_py}
    mesh.set_editor_property('nanite_settings', settings)
    unreal.EditorAssetLibrary.save_asset('{mesh_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_actor_material":
        actor_name = req.get("actor_name", "")
        material_path = req.get("material_path", "")
        slot_index = req.get("slot_index", 0)
        ue_script = f"""import unreal
mat = unreal.load_asset('{material_path}')
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == '{actor_name}':
        for comp in a.get_components_by_class(unreal.StaticMeshComponent):
            comp.set_material({slot_index}, mat)
        unreal.log(f'Set material on {actor_name}')
        break
"""
        return _exec_ue_script(ue_script, action)

    elif action == "apply_lumen_settings":
        gi_val = 1 if req.get("enable_gi", True) else 0
        refl_val = 1 if req.get("enable_reflections", True) else 0
        ue_script = f"""import unreal
world = unreal.EditorLevelLibrary.get_editor_world()
unreal.SystemLibrary.execute_console_command(world, 'r.Lumen.DiffuseIndirect.Allow {gi_val}')
unreal.SystemLibrary.execute_console_command(world, 'r.Lumen.Reflections.Allow {refl_val}')
"""
        return _exec_ue_script(ue_script, action)

    # ── Sequencer Tools ───────────────────────────────────────────────────────
    elif action == "create_level_sequence":
        sequence_name = req.get("sequence_name", "")
        save_path = req.get("save_path", "/Game/Sequences")
        duration_seconds = req.get("duration_seconds", 5.0)
        ue_script = f"""import unreal
factory = unreal.LevelSequenceFactoryNew()
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
seq = asset_tools.create_asset('{sequence_name}', '{save_path}', unreal.LevelSequence, factory)
if seq:
    seq.set_playback_end_seconds({duration_seconds})
    unreal.EditorAssetLibrary.save_asset(seq.get_path_name())
    unreal.log(f'Sequence: {{seq.get_path_name()}}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "add_actor_to_sequence":
        sequence_path = req.get("sequence_path", "")
        actor_name = req.get("actor_name", "")
        ue_script = f"""import unreal
seq = unreal.load_asset('{sequence_path}')
if seq:
    for a in unreal.EditorLevelLibrary.get_all_level_actors():
        if a.get_actor_label() == '{actor_name}':
            binding = seq.add_possessable(a)
            unreal.EditorAssetLibrary.save_asset('{sequence_path}')
            unreal.log(f'Bound {actor_name} to sequence')
            break
"""
        return _exec_ue_script(ue_script, action)

    elif action == "open_level_sequence":
        sequence_path = req.get("sequence_path", "")
        ue_script = f"""import unreal
seq = unreal.load_asset('{sequence_path}')
if seq:
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_sequence_length":
        sequence_path = req.get("sequence_path", "")
        start_frame = req.get("start_frame", 0)
        end_frame = req.get("end_frame", 150)
        fps = req.get("fps", 30)
        ue_script = f"""import unreal
seq = unreal.load_asset('{sequence_path}')
if seq:
    rate = unreal.FrameRate({fps}, 1)
    seq.set_display_rate(rate)
    seq.set_playback_start({start_frame})
    seq.set_playback_end({end_frame})
    unreal.EditorAssetLibrary.save_asset('{sequence_path}')
"""
        return _exec_ue_script(ue_script, action)

    # ── Niagara VFX Tools ─────────────────────────────────────────────────────
    elif action == "spawn_niagara_system":
        system_path = req.get("system_path", "")
        actor_name = req.get("actor_name", "")
        x = req.get("x", 0.0)
        y = req.get("y", 0.0)
        z = req.get("z", 0.0)
        ue_script = f"""import unreal
sys_asset = unreal.load_asset('{system_path}')
if sys_asset:
    loc = unreal.Vector({x}, {y}, {z})
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.NiagaraActor, loc)
    actor.set_actor_label('{actor_name}')
    comp = actor.get_component_by_class(unreal.NiagaraComponent)
    if comp:
        comp.set_asset(sys_asset)
    unreal.log(f'Spawned Niagara: {actor_name}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_niagara_float":
        actor_name = req.get("actor_name", "")
        variable_name = req.get("variable_name", "")
        value = req.get("value", 0.0)
        ue_script = f"""import unreal
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == '{actor_name}':
        comp = a.get_component_by_class(unreal.NiagaraComponent)
        if comp:
            comp.set_variable_float('{variable_name}', {value})
        break
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_niagara_bool":
        actor_name = req.get("actor_name", "")
        variable_name = req.get("variable_name", "")
        value_py = str(req.get("value", True))
        ue_script = f"""import unreal
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == '{actor_name}':
        comp = a.get_component_by_class(unreal.NiagaraComponent)
        if comp:
            comp.set_variable_bool('{variable_name}', {value_py})
        break
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_niagara_vector":
        actor_name = req.get("actor_name", "")
        variable_name = req.get("variable_name", "")
        x = req.get("x", 0.0)
        y = req.get("y", 0.0)
        z = req.get("z", 0.0)
        ue_script = f"""import unreal
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == '{actor_name}':
        comp = a.get_component_by_class(unreal.NiagaraComponent)
        if comp:
            comp.set_variable_vec3('{variable_name}', unreal.Vector({x}, {y}, {z}))
        break
"""
        return _exec_ue_script(ue_script, action)

    # ── World & Level Tools ───────────────────────────────────────────────────
    elif action == "run_console_command":
        command = req.get("command", "")
        ue_script = f"""import unreal
world = unreal.EditorLevelLibrary.get_editor_world()
unreal.SystemLibrary.execute_console_command(world, '{command}')
unreal.log(f'Console: {command}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "save_current_level":
        ue_script = f"""import unreal
unreal.EditorLoadingAndSavingUtils.save_current_level()
unreal.log('Level saved')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_world_gravity":
        gravity_z = req.get("gravity_z", -980.0)
        ue_script = f"""import unreal
world = unreal.EditorLevelLibrary.get_editor_world()
settings = world.get_world_settings()
settings.set_editor_property('global_gravity_z', {gravity_z})
"""
        return _exec_ue_script(ue_script, action)

    elif action == "spawn_sky_atmosphere":
        ue_script = f"""import unreal
loc = unreal.Vector(0, 0, 0)
sky = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkyAtmosphere, loc)
sky.set_actor_label('SkyAtmosphere')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "spawn_directional_light":
        actor_name = req.get("actor_name", "DirectionalLight")
        intensity = req.get("intensity", 10.0)
        pitch = req.get("pitch", -45.0)
        yaw = req.get("yaw", 0.0)
        ue_script = f"""import unreal
loc = unreal.Vector(0, 0, 500)
light = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, loc)
light.set_actor_label('{actor_name}')
light.set_actor_rotation(unreal.Rotator({pitch}, {yaw}, 0), False)
comp = light.get_component_by_class(unreal.DirectionalLightComponent)
if comp:
    comp.set_editor_property('intensity', {intensity})
"""
        return _exec_ue_script(ue_script, action)

    elif action == "spawn_exponential_fog":
        actor_name = req.get("actor_name", "ExponentialHeightFog")
        fog_density = req.get("fog_density", 0.02)
        start_distance = req.get("start_distance", 0.0)
        ue_script = f"""import unreal
loc = unreal.Vector(0, 0, 0)
fog = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.ExponentialHeightFog, loc)
fog.set_actor_label('{actor_name}')
comp = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
if comp:
    comp.set_editor_property('fog_density', {fog_density})
    comp.set_editor_property('start_distance', {start_distance})
"""
        return _exec_ue_script(ue_script, action)

    elif action == "create_post_process_volume":
        actor_name = req.get("actor_name", "PostProcessVolume")
        unbound_py = str(req.get("is_unbound", True))
        ue_script = f"""import unreal
loc = unreal.Vector(0, 0, 0)
ppv = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.PostProcessVolume, loc)
ppv.set_actor_label('{actor_name}')
ppv.set_editor_property('unbound', {unbound_py})
"""
        return _exec_ue_script(ue_script, action)

    # ── Asset Management Tools ────────────────────────────────────────────────
    elif action == "list_assets_by_class":
        asset_class = req.get("asset_class", "StaticMesh")
        search_path = req.get("search_path", "/Game")
        sync_fwd = SYNC_FOLDER.replace(chr(92), '/')
        ue_script = f"""import unreal, json
reg = unreal.AssetRegistry.get()
f = unreal.ARFilter(class_names=['{asset_class}'], search_recursive=True, package_paths=['{search_path}'])
assets = reg.get_assets(f)
result = {{'status': 'ok', 'class': '{asset_class}', 'count': len(assets), 'assets': [str(a.package_name) for a in assets[:100]]}}
with open('{sync_fwd}/asset_list.json', 'w') as fp:
    json.dump(result, fp)
"""
        _exec_ue_script(ue_script, action)
        res_file = os.path.join(SYNC_FOLDER, "asset_list.json")
        try:
            with open(res_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"status": "error", "message": "Failed to read result"}

    elif action == "duplicate_asset":
        source_path = req.get("source_path", "")
        new_path = req.get("new_path", "")
        ue_script = f"""import unreal
result = unreal.EditorAssetLibrary.duplicate_asset('{source_path}', '{new_path}')
if result:
    unreal.EditorAssetLibrary.save_asset('{new_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "delete_asset":
        asset_path = req.get("asset_path", "")
        ue_script = f"""import unreal
unreal.EditorAssetLibrary.delete_asset('{asset_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "rename_asset":
        source_path = req.get("source_path", "")
        destination_path = req.get("destination_path", "")
        ue_script = f"""import unreal
unreal.EditorAssetLibrary.rename_asset('{source_path}', '{destination_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "find_actors_by_tag":
        tag = req.get("tag", "")
        sync_fwd = SYNC_FOLDER.replace(chr(92), '/')
        ue_script = f"""import unreal, json
all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
matches = [a.get_actor_label() for a in all_actors if '{tag}' in [str(t) for t in a.tags]]
result = {{'status': 'ok', 'tag': '{tag}', 'count': len(matches), 'actors': matches}}
with open('{sync_fwd}/actors_by_tag.json', 'w') as fp:
    json.dump(result, fp)
"""
        _exec_ue_script(ue_script, action)
        res_file = os.path.join(SYNC_FOLDER, "actors_by_tag.json")
        try:
            with open(res_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"status": "error", "message": "Failed to read result"}

    elif action == "set_actor_tag":
        actor_name = req.get("actor_name", "")
        tag = req.get("tag", "")
        ue_script = f"""import unreal
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == '{actor_name}':
        tags = list(a.tags)
        if '{tag}' not in [str(t) for t in tags]:
            a.tags = tags + [unreal.Name('{tag}')]
        unreal.log(f'Tag added: {tag}')
        break
"""
        return _exec_ue_script(ue_script, action)

    elif action == "create_content_folder":
        folder_path = req.get("folder_path", "")
        ue_script = f"""import unreal
unreal.EditorAssetLibrary.make_directory('{folder_path}')
"""
        return _exec_ue_script(ue_script, action)

    # ── Physics & Collision Tools ─────────────────────────────────────────────
    elif action == "set_actor_physics":
        actor_name = req.get("actor_name", "")
        phys_py = str(req.get("enabled", False))
        grav_py = str(req.get("gravity_enabled", True))
        ue_script = f"""import unreal
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == '{actor_name}':
        for comp in a.get_components_by_class(unreal.PrimitiveComponent):
            comp.set_simulate_physics({phys_py})
            comp.set_enable_gravity({grav_py})
        break
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_collision_profile":
        actor_name = req.get("actor_name", "")
        profile_name = req.get("profile_name", "BlockAll")
        ue_script = f"""import unreal
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == '{actor_name}':
        for comp in a.get_components_by_class(unreal.PrimitiveComponent):
            comp.set_collision_profile_name('{profile_name}')
        break
"""
        return _exec_ue_script(ue_script, action)

    elif action == "generate_mesh_collision":
        mesh_path = req.get("mesh_path", "")
        method = req.get("method", "box")
        ue_script = f"""import unreal
mesh = unreal.load_asset('{mesh_path}')
if mesh:
    shape_map = {{
        'box': unreal.ScriptingCollisionShapeType.BOX,
        'sphere': unreal.ScriptingCollisionShapeType.SPHERE,
        'capsule': unreal.ScriptingCollisionShapeType.CAPSULE,
        'convex': unreal.ScriptingCollisionShapeType.NDOP26,
    }}
    method = '{method}'
    if method == 'complex_as_simple':
        mesh.set_editor_property('use_complex_as_simple_collision', True)
    elif method in shape_map:
        unreal.EditorStaticMeshLibrary.remove_collisions(mesh)
        unreal.EditorStaticMeshLibrary.add_simple_collisions(mesh, shape_map[method])
    unreal.EditorAssetLibrary.save_asset('{mesh_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "remove_mesh_collision":
        mesh_path = req.get("mesh_path", "")
        ue_script = f"""import unreal
mesh = unreal.load_asset('{mesh_path}')
if mesh:
    unreal.EditorStaticMeshLibrary.remove_collisions(mesh)
    unreal.EditorAssetLibrary.save_asset('{mesh_path}')
"""
        return _exec_ue_script(ue_script, action)

    elif action == "set_actor_mass":
        actor_name = req.get("actor_name", "")
        mass_kg = req.get("mass_kg", 1.0)
        ue_script = f"""import unreal
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_actor_label() == '{actor_name}':
        for comp in a.get_components_by_class(unreal.PrimitiveComponent):
            comp.set_editor_property('override_mass', True)
            comp.set_editor_property('mass', {mass_kg})
        break
"""
        return _exec_ue_script(ue_script, action)

    else:
        return {"status": "error", "message": f"Unknown action: {action}"}


def handle_client(client_socket: socket.socket):
    """Handle one incoming connection from the MCP bridge."""
    try:
        chunks = []
        while True:
            chunk = client_socket.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            # Stop when we have a complete JSON payload
            try:
                json.loads(b"".join(chunks).decode("utf-8"))
                break   # valid JSON received
            except json.JSONDecodeError:
                continue  # keep reading

        raw = b"".join(chunks).decode("utf-8").strip()
        if not raw:
            send_response(client_socket, {"status": "error", "message": "Empty request"})
            return

        req = json.loads(raw)

        # Auth check
        if req.get("auth_token") != AUTH_TOKEN:
            send_response(client_socket, {"status": "error", "message": "Invalid auth token"})
            return

        action = req.get("action", "")
        print(f"[UnrealServer] Action: {action}")

        result = handle_action(req)
        send_response(client_socket, result)

    except Exception as exc:
        send_response(client_socket, {"status": "error", "message": str(exc)})
    finally:
        client_socket.close()


def send_response(sock: socket.socket, data: dict):
    raw = json.dumps(data).encode("utf-8")
    sock.sendall(raw)


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(16)
    print(f"[UnrealServer] Listening on {LISTEN_HOST}:{LISTEN_PORT}")
    print(f"[UnrealServer] Forwarding to Unreal Remote Control on port {UNREAL_PORT}")
    print(f"[UnrealServer] Sync folder: {SYNC_FOLDER}")
    print("[UnrealServer] Ready. Keep this window open while using AI tools.")
    print("-" * 60)

    try:
        while True:
            client_sock, addr = server.accept()
            print(f"[UnrealServer] Connection from {addr}")
            t = threading.Thread(target=handle_client, args=(client_sock,), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[UnrealServer] Shutting down.")
        server.close()


if __name__ == "__main__":
    main()
