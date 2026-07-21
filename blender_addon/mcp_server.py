import sys
import json
import socket
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dropbox_memory
from mcp.server.fastmcp import FastMCP, Image

# Define the MCP server
mcp = FastMCP("UnrealBlenderSync")

# Configuration for the socket connection to Blender
BLENDER_HOST = "127.0.0.1"
BLENDER_PORT = 12345

def send_to_blender(command: dict) -> dict:
    """Sends a JSON command to the Blender socket server and waits for a response."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(30.0)
            s.connect((BLENDER_HOST, BLENDER_PORT))
            s.sendall(json.dumps(command).encode('utf-8'))
            s.shutdown(socket.SHUT_WR)  # Signal we're done sending
            
            # Read all response data
            chunks = []
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            data = b''.join(chunks)
            if not data:
                return {"status": "error", "message": "No response from Blender"}
            return json.loads(data.decode('utf-8'))
    except ConnectionRefusedError:
        return {"status": "error", "message": "Could not connect to Blender. Is the AI Bridge running?"}
    except Exception as e:
        return {"status": "error", "message": f"Socket error: {str(e)}"}



@mcp.tool()
def get_scene_hierarchy() -> str:
    """Lists all objects in the current active Blender scene."""
    response = send_to_blender({"action": "get_scene_hierarchy"})
    if response.get("status") == "success":
        objects = response.get("data", [])
        if not objects:
            return "The Blender scene is empty."
        return "\n".join([f"- {obj['name']} ({obj['type']})" for obj in objects])
    return f"Error: {response.get('message')}"


@mcp.tool()
def trigger_sync(export_type: str = "ALL") -> str:
    """
    Triggers the FBX export pipeline in Blender.
    export_type can be 'ALL' (mesh+anim), 'MESH' (mesh only), or 'ANIM' (animation only).
    """
    response = send_to_blender({"action": "trigger_sync", "type": export_type.upper()})
    if response.get("status") == "success":
        return f"Successfully triggered {export_type} export in Blender."
    return f"Failed to export: {response.get('message')}"


@mcp.tool()
def rename_object(old_name: str, new_name: str) -> str:
    """Renames an object in the active Blender scene."""
    response = send_to_blender({
        "action": "rename_object",
        "old_name": old_name,
        "new_name": new_name
    })
    if response.get("status") == "success":
        return f"Successfully renamed '{old_name}' to '{new_name}'."
    return f"Failed to rename: {response.get('message')}"

@mcp.tool()
def execute_blender_python(script: str) -> str:
    """God Mode: Execute an arbitrary Python (bpy) script directly inside Blender and return its output."""
    response = send_to_blender({"action": "execute_python", "script": script})
    if response.get("status") == "success":
        return response.get("output", "Script executed successfully (no output).")
    return f"Failed: {response.get('message')}\nTraceback:\n{response.get('traceback', '')}"


@mcp.tool()
def create_primitive(type: str = "CUBE", name: str = "", location: list = [0,0,0], size: float = 2.0) -> str:
    """Create a mesh primitive in Blender. type can be: CUBE, SPHERE, CYLINDER, PLANE, CONE, TORUS, MONKEY, EMPTY, CAMERA, LIGHT."""
    response = send_to_blender({"action": "create_primitive", "type": type, "name": name, "location": location, "size": size})
    if response.get("status") == "success":
        return f"Created {type} with name '{response.get('name')}'."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def delete_object(name: str) -> str:
    """Delete an object from the Blender scene by name."""
    response = send_to_blender({"action": "delete_object", "name": name})
    if response.get("status") == "success":
        return f"Deleted '{name}'."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def set_transform(name: str, location: list = None, rotation: list = None, scale: list = None) -> str:
    """Move, rotate, or scale an object. Rotation is in degrees [X, Y, Z]. Scale is a multiplier [X, Y, Z]."""
    cmd = {"action": "set_transform", "name": name}
    if location is not None: cmd["location"] = location
    if rotation is not None: cmd["rotation"] = rotation
    if scale is not None: cmd["scale"] = scale
    response = send_to_blender(cmd)
    if response.get("status") == "success":
        return f"Transform updated for '{name}'."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def create_material(name: str, color: list = [1.0, 1.0, 1.0, 1.0], metallic: float = 0.0, roughness: float = 0.5) -> str:
    """Create a PBR material. color is [R, G, B, A] with values 0.0-1.0."""
    response = send_to_blender({"action": "create_material", "name": name, "color": color, "metallic": metallic, "roughness": roughness})
    if response.get("status") == "success":
        return f"Material '{response.get('name')}' created."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def set_object_material(object: str, material: str) -> str:
    """Assign an existing material to an object. Both must already exist in the scene."""
    response = send_to_blender({"action": "set_object_material", "object": object, "material": material})
    if response.get("status") == "success":
        return f"Material '{material}' assigned to '{object}'."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def get_object_info(name: str) -> str:
    """Get detailed info (location, rotation, scale, materials) about a specific object."""
    response = send_to_blender({"action": "get_object_info", "name": name})
    if response.get("status") == "success":
        d = response.get("data", {})
        return "\n".join([f"{k}: {v}" for k, v in d.items()])
    return f"Failed: {response.get('message')}"


@mcp.tool()
def set_keyframe(name: str, frame: int, data_path: str = "location") -> str:
    """Insert a keyframe on an object at a specific frame. data_path can be: location, rotation_euler, scale."""
    response = send_to_blender({"action": "set_keyframe", "name": name, "frame": frame, "data_path": data_path})
    if response.get("status") == "success":
        return f"Keyframe inserted on '{name}' at frame {frame} for '{data_path}'."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def set_timeline(start: int = 1, end: int = 250, fps: int = 24) -> str:
    """Set the scene timeline start/end frames and FPS."""
    response = send_to_blender({"action": "set_timeline", "start": start, "end": end, "fps": fps})
    if response.get("status") == "success":
        return f"Timeline set: frames {start}-{end} at {fps} FPS."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def render_frame(output_path: str = "//render.png", frame: int = 1) -> str:
    """Render a single frame and save it to disk. output_path can use // for relative to .blend file."""
    response = send_to_blender({"action": "render_frame", "output_path": output_path, "frame": frame})
    if response.get("status") == "success":
        return f"Rendered frame {frame} to '{output_path}'."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def set_render_settings(resolution_x: int = None, resolution_y: int = None, engine: str = None, samples: int = None) -> str:
    """Configure render settings. engine can be: CYCLES or BLENDER_EEVEE."""
    cmd = {"action": "set_render_settings"}
    if resolution_x: cmd["resolution_x"] = resolution_x
    if resolution_y: cmd["resolution_y"] = resolution_y
    if engine: cmd["engine"] = engine
    if samples: cmd["samples"] = samples
    response = send_to_blender(cmd)
    if response.get("status") == "success":
        return "Render settings updated."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def add_light(name: str = "NewLight", light_type: str = "POINT", location: list = [0,0,5], energy: float = 1000.0, color: list = [1.0, 1.0, 1.0]) -> str:
    """Add a light to the scene. light_type can be: POINT, SUN, SPOT, AREA."""
    response = send_to_blender({"action": "add_light", "name": name, "light_type": light_type, "location": location, "energy": energy, "color": color})
    if response.get("status") == "success":
        return f"{light_type} light '{response.get('name')}' added."
    return f"Failed: {response.get('message')}"


UNREAL_HOST = "127.0.0.1"
UNREAL_PORT = 8001
AUTH_TOKEN = "d9a7f3e8b6c04a92a5f2e1c4b9d7e3a1"

def send_to_unreal(command: dict) -> dict:
    """Sends a JSON command to the Unreal socket server and waits for a response."""
    try:
        payload = {"auth_token": AUTH_TOKEN, **command}
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(30.0)
            s.connect((UNREAL_HOST, UNREAL_PORT))
            s.sendall(json.dumps(payload).encode('utf-8'))
            s.shutdown(socket.SHUT_WR)  # Signal we're done sending
            
            # Read all response data
            chunks = []
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            data = b''.join(chunks)
            if not data:
                return {"status": "error", "message": "No response from Unreal"}
            return json.loads(data.decode('utf-8'))
    except Exception as e:
        return {"status": "error", "message": f"Socket error to Unreal: {str(e)}"}


@mcp.tool()
def take_screenshot() -> Image:
    """Take a screenshot of the Blender active viewport/window and return it as an image."""
    response = send_to_blender({"action": "take_screenshot"})
    if response.get("status") == "success":
        return Image(path=response.get("filepath"))
    raise RuntimeError(f"Failed to capture screenshot: {response.get('message')}")


@mcp.tool()
def create_pcg_component(graph_path: str, actor_name: str = "", location: list = [0,0,0], scale: list = [1,1,1]) -> str:
    """Spawn a PCG component on an actor or create a new PCG Actor/Volume in Unreal Engine."""
    loc_dict = {"x": location[0], "y": location[1], "z": location[2]} if len(location) == 3 else {"x": 0, "y": 0, "z": 0}
    scl_dict = {"x": scale[0], "y": scale[1], "z": scale[2]} if len(scale) == 3 else {"x": 1, "y": 1, "z": 1}
    response = send_to_unreal({
        "action": "create_pcg_component",
        "actor_name": actor_name,
        "graph_path": graph_path,
        "location": loc_dict,
        "scale": scl_dict
    })
    if response.get("status") in ("success", "ok"):
        return f"Successfully created PCG component with graph '{graph_path}'."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def pcg_generate(actor_name: str) -> str:
    """Trigger generation on a PCG component in Unreal Engine."""
    response = send_to_unreal({"action": "pcg_generate", "actor_name": actor_name})
    if response.get("status") in ("success", "ok"):
        return f"Successfully triggered PCG generation on '{actor_name}'."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def pcg_cleanup(actor_name: str) -> str:
    """Clean up the generated resources of a PCG component in Unreal Engine."""
    response = send_to_unreal({"action": "pcg_cleanup", "actor_name": actor_name})
    if response.get("status") in ("success", "ok"):
        return f"Successfully cleaned up PCG on '{actor_name}'."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def pcg_set_parameter(actor_name: str, parameter_name: str, value: str, value_type: str = "") -> str:
    """Set or override a parameter on a PCG Graph Instance in Unreal. value can be a JSON string, list/dict representation if vector/rotator is set."""
    try:
        parsed_val = json.loads(value)
    except:
        parsed_val = value

    response = send_to_unreal({
        "action": "pcg_set_parameter",
        "actor_name": actor_name,
        "parameter_name": parameter_name,
        "value": parsed_val,
        "value_type": value_type
    })
    if response.get("status") in ("success", "ok"):
        return f"Successfully set PCG parameter '{parameter_name}' to {value}."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def pcg_get_parameters(actor_name: str) -> str:
    """Retrieve information and parameter overrides status from a PCG component in Unreal."""
    response = send_to_unreal({"action": "pcg_get_parameters", "actor_name": actor_name})
    return json.dumps(response, indent=2)


@mcp.tool()
def align_actors(actor_a_name: str, actor_b_name: str, axis: str = "+X", offset: float = 0.0) -> str:
    """Precisely align actor B next to actor A along a specified axis (+X, -X, +Y, -Y, +Z, -Z) in Unreal so they touch exactly (no gap, no overlap)."""
    response = send_to_unreal({
        "action": "align_actors",
        "actor_a_name": actor_a_name,
        "actor_b_name": actor_b_name,
        "axis": axis,
        "offset": offset
    })
    if response.get("status") in ("success", "ok"):
        return f"Successfully aligned '{actor_b_name}' next to '{actor_a_name}' along {axis} (offset: {offset})."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def get_actor_dimensions(actor_name: str) -> str:
    """Get world-space bounding box size (cm), min/max extents, and origin of an actor in Unreal.
    Always call this BEFORE placing adjacent actors to know exact measurements."""
    response = send_to_unreal({"action": "get_actor_dimensions", "actor_name": actor_name})
    return json.dumps(response, indent=2)


@mcp.tool()
def snap_to_grid(actor_name: str, grid_size: float = 100.0) -> str:
    """Snap an actor's location to the nearest grid unit (in cm) in Unreal.
    grid_size=100 means 1 meter grid. Ensures actors sit on exact coordinates."""
    response = send_to_unreal({
        "action": "snap_to_grid",
        "actor_name": actor_name,
        "grid_size": grid_size
    })
    if response.get("status") in ("success", "ok"):
        return f"Snapped '{actor_name}' to grid (size: {grid_size} cm)."
    return f"Failed: {response.get('message')}"


@mcp.tool()
def verify_actor_alignment(actor_a_name: str, actor_b_name: str, axis: str = "X") -> str:
    """Check whether two actors are touching perfectly, overlapping, or have a gap in Unreal.
    Returns alignment_status: TOUCHING_PERFECTLY | GAP | OVERLAPPING | TOUCHING_PERFECTLY_REVERSED
    and exact gap in cm. Always call this after align_actors to confirm correctness.
    If is_correct is False, use align_actors again to fix."""
    response = send_to_unreal({
        "action": "verify_actor_alignment",
        "actor_a_name": actor_a_name,
        "actor_b_name": actor_b_name,
        "axis": axis
    })
    if response.get("status") in ("success", "ok"):
        status = response.get("alignment_status", "UNKNOWN")
        gap_ab = response.get("gap_a_to_b_cm", "N/A")
        gap_ba = response.get("gap_b_to_a_cm", "N/A")
        is_correct = response.get("is_correct", False)
        summary = (
            f"Alignment [{axis} axis]: {status}\n"
            f"  Gap A→B: {gap_ab} cm | Gap B→A: {gap_ba} cm\n"
            f"  ✅ CORRECT" if is_correct else
            f"  ❌ NEEDS FIX (gap or overlap detected)"
        )
        return summary
    return f"Failed: {response.get('message')}\nFull response: {json.dumps(response, indent=2)}"



@mcp.tool()
def create_geometry_nodes_modifier(name: str, group_name: str = "GeometryNodes") -> str:
    response = send_to_blender({"action": "create_geometry_nodes_modifier", "name": name, "group_name": group_name})
    return json.dumps(response, indent=2)

@mcp.tool()
def add_geometry_node(group_name: str, node_type: str, node_name: str = "", location_x: float = 0, location_y: float = 0) -> str:
    response = send_to_blender({"action": "add_geometry_node", "group_name": group_name, "node_type": node_type, "node_name": node_name, "location_x": location_x, "location_y": location_y})
    return json.dumps(response, indent=2)

@mcp.tool()
def link_geometry_nodes(group_name: str, from_node: str, to_node: str, from_socket: int = 0, to_socket: int = 0) -> str:
    response = send_to_blender({"action": "link_geometry_nodes", "group_name": group_name, "from_node": from_node, "to_node": to_node, "from_socket": from_socket, "to_socket": to_socket})
    return json.dumps(response, indent=2)

@mcp.tool()
def set_geometry_node_value(group_name: str, node_name: str, value: str, socket_index: int = 0) -> str:
    response = send_to_blender({"action": "set_geometry_node_value", "group_name": group_name, "node_name": node_name, "value": value, "socket_index": socket_index})
    return json.dumps(response, indent=2)

@mcp.tool()
def list_geometry_nodes(group_name: str) -> str:
    response = send_to_blender({"action": "list_geometry_nodes", "group_name": group_name})
    return json.dumps(response, indent=2)

@mcp.tool()
def add_modifier(name: str, modifier_type: str = "SUBSURF", modifier_name: str = "") -> str:
    response = send_to_blender({"action": "add_modifier", "name": name, "modifier_type": modifier_type, "modifier_name": modifier_name})
    return json.dumps(response, indent=2)

@mcp.tool()
def remove_modifier(name: str, modifier_name: str) -> str:
    response = send_to_blender({"action": "remove_modifier", "name": name, "modifier_name": modifier_name})
    return json.dumps(response, indent=2)

@mcp.tool()
def apply_modifier(name: str, modifier_name: str) -> str:
    response = send_to_blender({"action": "apply_modifier", "name": name, "modifier_name": modifier_name})
    return json.dumps(response, indent=2)

@mcp.tool()
def set_modifier_property(name: str, modifier_name: str, property_name: str, value: str) -> str:
    response = send_to_blender({"action": "set_modifier_property", "name": name, "modifier_name": modifier_name, "property_name": property_name, "value": value})
    return json.dumps(response, indent=2)

@mcp.tool()
def list_modifiers(name: str) -> str:
    response = send_to_blender({"action": "list_modifiers", "name": name})
    return json.dumps(response, indent=2)

@mcp.tool()
def uv_unwrap(name: str, method: str = "smart") -> str:
    response = send_to_blender({"action": "uv_unwrap", "name": name, "method": method})
    return json.dumps(response, indent=2)

@mcp.tool()
def pack_uv_islands(name: str) -> str:
    response = send_to_blender({"action": "pack_uv_islands", "name": name})
    return json.dumps(response, indent=2)

@mcp.tool()
def create_image_texture(image_name: str = "NewImage", width: int = 1024, height: int = 1024, color: list = [0.0, 0.0, 0.0, 1.0]) -> str:
    response = send_to_blender({"action": "create_image_texture", "image_name": image_name, "width": width, "height": height, "color": color})
    return json.dumps(response, indent=2)

@mcp.tool()
def save_image(image_name: str, filepath: str) -> str:
    response = send_to_blender({"action": "save_image", "image_name": image_name, "filepath": filepath})
    return json.dumps(response, indent=2)

@mcp.tool()
def add_shader_node(material_name: str, node_type: str, node_name: str = "", location_x: float = 0, location_y: float = 0) -> str:
    response = send_to_blender({"action": "add_shader_node", "material_name": material_name, "node_type": node_type, "node_name": node_name, "location_x": location_x, "location_y": location_y})
    return json.dumps(response, indent=2)

@mcp.tool()
def link_shader_nodes(material_name: str, from_node: str, to_node: str, from_socket: int = 0, to_socket: int = 0) -> str:
    response = send_to_blender({"action": "link_shader_nodes", "material_name": material_name, "from_node": from_node, "to_node": to_node, "from_socket": from_socket, "to_socket": to_socket})
    return json.dumps(response, indent=2)

@mcp.tool()
def set_shader_node_value(material_name: str, node_name: str, value: str, socket_index: int = 0) -> str:
    try:
        val = json.loads(value)
    except:
        val = value
    response = send_to_blender({"action": "set_shader_node_value", "material_name": material_name, "node_name": node_name, "value": val, "socket_index": socket_index})
    return json.dumps(response, indent=2)

@mcp.tool()
def create_full_pbr_material(material_name: str = "NewPBRMaterial", base_color: list = [0.8, 0.8, 0.8, 1.0], metallic: float = 0.0, roughness: float = 0.5, emission_strength: float = 0.0) -> str:
    response = send_to_blender({"action": "create_full_pbr_material", "material_name": material_name, "base_color": base_color, "metallic": metallic, "roughness": roughness, "emission_strength": emission_strength})
    return json.dumps(response, indent=2)

@mcp.tool()
def get_material_nodes(material_name: str) -> str:
    response = send_to_blender({"action": "get_material_nodes", "material_name": material_name})
    return json.dumps(response, indent=2)

@mcp.tool()
def export_fbx(filepath: str = "", selected_only: bool = False, scale_factor: float = 1.0) -> str:
    response = send_to_blender({"action": "export_fbx", "filepath": filepath, "selected_only": selected_only, "scale_factor": scale_factor})
    return json.dumps(response, indent=2)

@mcp.tool()
def export_gltf(filepath: str = "", format: str = "GLB", selected_only: bool = False) -> str:
    response = send_to_blender({"action": "export_gltf", "filepath": filepath, "format": format, "selected_only": selected_only})
    return json.dumps(response, indent=2)

@mcp.tool()
def export_obj(filepath: str = "", selected_only: bool = False) -> str:
    response = send_to_blender({"action": "export_obj", "filepath": filepath, "selected_only": selected_only})
    return json.dumps(response, indent=2)

@mcp.tool()
def import_obj(filepath: str) -> str:
    response = send_to_blender({"action": "import_obj", "filepath": filepath})
    return json.dumps(response, indent=2)

@mcp.tool()
def import_gltf(filepath: str) -> str:
    response = send_to_blender({"action": "import_gltf", "filepath": filepath})
    return json.dumps(response, indent=2)

@mcp.tool()
def export_alembic(filepath: str = "", start_frame: int = -1, end_frame: int = -1) -> str:
    args = {"action": "export_alembic", "filepath": filepath}
    if start_frame != -1: args["start_frame"] = start_frame
    if end_frame != -1: args["end_frame"] = end_frame
    response = send_to_blender(args)
    return json.dumps(response, indent=2)

@mcp.tool()
def create_action(name: str, action_name: str = "NewAction") -> str:
    response = send_to_blender({"action": "create_action", "name": name, "action_name": action_name})
    return json.dumps(response, indent=2)

@mcp.tool()
def push_to_nla(name: str, track_name: str = "NLATrack") -> str:
    response = send_to_blender({"action": "push_to_nla", "name": name, "track_name": track_name})
    return json.dumps(response, indent=2)

@mcp.tool()
def clear_animation(name: str) -> str:
    response = send_to_blender({"action": "clear_animation", "name": name})
    return json.dumps(response, indent=2)

@mcp.tool()
def set_bone_pose_rotation(armature_name: str, bone_name: str, rotation_mode: str = "QUATERNION", values: list = [1, 0, 0, 0]) -> str:
    response = send_to_blender({"action": "set_bone_pose_rotation", "armature_name": armature_name, "bone_name": bone_name, "rotation_mode": rotation_mode, "values": values})
    return json.dumps(response, indent=2)

@mcp.tool()
def add_rigid_body(name: str, rb_type: str = "ACTIVE", mass: float = 1.0) -> str:
    response = send_to_blender({"action": "add_rigid_body", "name": name, "rb_type": rb_type, "mass": mass})
    return json.dumps(response, indent=2)

@mcp.tool()
def add_cloth_simulation(name: str) -> str:
    response = send_to_blender({"action": "add_cloth_simulation", "name": name})
    return json.dumps(response, indent=2)

@mcp.tool()
def add_particle_system(name: str, particle_type: str = "EMITTER", count: int = 1000, lifetime: int = 50) -> str:
    response = send_to_blender({"action": "add_particle_system", "name": name, "particle_type": particle_type, "count": count, "lifetime": lifetime})
    return json.dumps(response, indent=2)

@mcp.tool()
def bake_physics() -> str:
    response = send_to_blender({"action": "bake_physics"})
    return json.dumps(response, indent=2)

@mcp.tool()
def setup_compositor(output_path: str = "//compositor_output/") -> str:
    response = send_to_blender({"action": "setup_compositor", "output_path": output_path})
    return json.dumps(response, indent=2)

@mcp.tool()
def add_compositor_node(node_type: str, node_name: str = "", location_x: float = 0, location_y: float = 0) -> str:
    response = send_to_blender({"action": "add_compositor_node", "node_type": node_type, "node_name": node_name, "location_x": location_x, "location_y": location_y})
    return json.dumps(response, indent=2)

@mcp.tool()
def link_compositor_nodes(from_node: str, to_node: str, from_socket: int = 0, to_socket: int = 0) -> str:
    response = send_to_blender({"action": "link_compositor_nodes", "from_node": from_node, "to_node": to_node, "from_socket": from_socket, "to_socket": to_socket})
    return json.dumps(response, indent=2)

@mcp.tool()
def set_render_pass(pass_name: str = "ao") -> str:
    response = send_to_blender({"action": "set_render_pass", "pass_name": pass_name})
    return json.dumps(response, indent=2)

@mcp.tool()
def duplicate_object(name: str, new_name: str = "", offset_x: float = 0, offset_y: float = 0, offset_z: float = 0) -> str:
    response = send_to_blender({"action": "duplicate_object", "name": name, "new_name": new_name, "offset_x": offset_x, "offset_y": offset_y, "offset_z": offset_z})
    return json.dumps(response, indent=2)

@mcp.tool()
def select_objects_by_type(object_type: str = "MESH") -> str:
    response = send_to_blender({"action": "select_objects_by_type", "object_type": object_type})
    return json.dumps(response, indent=2)

@mcp.tool()
def join_objects(object_names: list, result_name: str = "") -> str:
    response = send_to_blender({"action": "join_objects", "object_names": object_names, "result_name": result_name})
    return json.dumps(response, indent=2)

@mcp.tool()
def set_origin(name: str, origin_type: str = "ORIGIN_CENTER_OF_MASS") -> str:
    response = send_to_blender({"action": "set_origin", "name": name, "origin_type": origin_type})
    return json.dumps(response, indent=2)

@mcp.tool()
def check_project_plans(project_name: str, dropbox_path: str) -> str:
    """Reads AI_Plans/{project_name}/plans.json from Dropbox."""
    return json.dumps(dropbox_memory.check_project_plans(project_name, dropbox_path))

@mcp.tool()
def register_active_task(project_name: str, dropbox_path: str, task_id: str, author: str, engine: str, task_description: str, location: str) -> str:
    """Adds a PLANNED/IN_PROGRESS entry."""
    return json.dumps(dropbox_memory.register_active_task(project_name, dropbox_path, task_id, author, engine, task_description, location))

@mcp.tool()
def complete_active_task(project_name: str, dropbox_path: str, task_id: str, status: str, notes: str, assets: list) -> str:
    """Marks task DONE."""
    return json.dumps(dropbox_memory.complete_active_task(project_name, dropbox_path, task_id, status, notes, assets))

@mcp.tool()
def apply_animation_to_character(filepath: str, target_object: str = "") -> str:
    """Apply animation from FBX/BVH to character."""
    response = send_to_blender({"action": "apply_animation_to_character", "filepath": filepath, "target_object": target_object})
    return json.dumps(response, indent=2)

@mcp.tool()
def initialize_project_brain(project_name: str, dropbox_path: str) -> str:
    """Lead AI initializes the folder structure and generates a Universal Prompt."""
    return json.dumps(dropbox_memory.initialize_project_brain(project_name, dropbox_path))

@mcp.tool()
def add_research_note(project_name: str, dropbox_path: str, topic: str, content: str) -> str:
    """Creates or overwrites a Markdown research note."""
    return json.dumps(dropbox_memory.add_research_note(project_name, dropbox_path, topic, content))

@mcp.tool()
def read_research_notes(project_name: str, dropbox_path: str) -> str:
    """Lists all research notes and returns their content and validation status."""
    return json.dumps(dropbox_memory.read_research_notes(project_name, dropbox_path))

@mcp.tool()
def validate_code_snippet(project_name: str, dropbox_path: str, topic: str, is_good: bool, notes: str) -> str:
    """Appends a validation header to an existing research note."""
    return json.dumps(dropbox_memory.validate_code_snippet(project_name, dropbox_path, topic, is_good, notes))

if __name__ == "__main__":
    # Run the MCP stdio server
    # Configured in Claude Desktop: Settings -> Developer -> Edit Config
    mcp.run()

