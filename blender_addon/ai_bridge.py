import bpy
import threading
import socket
import json
import queue

# Queue to execute Blender operations in the main thread
execution_queue = queue.Queue()

# Global state
server_socket = None
server_thread = None
is_running = False

def handle_client(conn, addr):
    """Handles incoming socket commands."""
    try:
        conn.settimeout(30.0)
        # Read all incoming data until client signals done
        chunks = []
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
        data = b''.join(chunks)
        if not data:
            return
            
        command = json.loads(data.decode('utf-8'))
        action = command.get("action")
        
        # We need a way to get the result from the main thread
        result_queue = queue.Queue()
        execution_queue.put((action, command, result_queue))
        
        # Wait for the main thread to execute the command
        result = result_queue.get(timeout=60.0)
        
        conn.sendall(json.dumps(result).encode('utf-8'))
    except Exception as e:
        print(f"AI Bridge Error handling client: {e}")
    finally:
        conn.close()


def server_loop():
    """Runs the socket server on a background thread."""
    global server_socket, is_running
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind(("127.0.0.1", 12345))
        server_socket.listen(5)
        is_running = True
        print("AI Bridge listening on 127.0.0.1:12345...")
        
        while is_running:
            try:
                server_socket.settimeout(1.0)
                conn, addr = server_socket.accept()
                
                # Handle client in a new thread so we don't block
                t = threading.Thread(target=handle_client, args=(conn, addr))
                t.daemon = True
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if is_running:
                    print(f"AI Bridge Server error: {e}")
                break
    finally:
        if server_socket:
            server_socket.close()
            server_socket = None
        is_running = False
        print("AI Bridge stopped.")

def process_execution_queue():
    """Timer callback to process queued commands in Blender's main thread."""
    if not is_running:
        return None
        
    try:
        while True:
            action, command, result_queue = execution_queue.get_nowait()
            
            try:
                if action == "get_scene_hierarchy":
                    objects = [{"name": obj.name, "type": obj.type} for obj in bpy.context.scene.objects]
                    result_queue.put({"status": "success", "data": objects})
                    
                elif action == "trigger_sync":
                    export_type = command.get("type", "ALL")
                    if export_type == "MESH":
                        bpy.ops.ubsync.export_mesh_only()
                    elif export_type == "ANIM":
                        bpy.ops.ubsync.export_anim_only()
                    else:
                        bpy.ops.ubsync.export_to_unreal()
                    result_queue.put({"status": "success"})
                    
                elif action == "get_metadata":
                    # Returns the entire metadata dict stored in sync folder
                    try:
                        from .utils import get_sync_dir
                        from .metadata import load_metadata
                        sync_dir = get_sync_dir(bpy.context)
                        if sync_dir:
                            data = load_metadata(sync_dir)
                            result_queue.put({"status": "success", "metadata": data})
                        else:
                            result_queue.put({"status": "error", "message": "Sync folder not configured."})
                    except Exception as e:
                        result_queue.put({"status": "error", "message": str(e)})
                
                elif action == "set_metadata":
                    # Expects a JSON-serializable dict under "metadata"
                    try:
                        from .utils import get_sync_dir
                        from .metadata import save_metadata
                        sync_dir = get_sync_dir(bpy.context)
                        if sync_dir:
                            meta = command.get("metadata", {})
                            save_metadata(sync_dir, meta)
                            result_queue.put({"status": "success"})
                        else:
                            result_queue.put({"status": "error", "message": "Sync folder not configured."})
                    except Exception as e:
                        result_queue.put({"status": "error", "message": str(e)})
                
                elif action == "get_sync_dir":
                    # Returns the sync directory configured in the add-on preferences
                    try:
                        from .utils import get_sync_dir
                        sync_dir = get_sync_dir(bpy.context)
                        if sync_dir:
                            result_queue.put({"status": "success", "sync_dir": sync_dir})
                        else:
                            result_queue.put({"status": "error", "message": "Sync folder not configured."})
                    except Exception as e:
                        result_queue.put({"status": "error", "message": str(e)})

                elif action == "execute_python":
                    script = command.get("script", "")
                    import sys
                    import io
                    import traceback as tb
                    # Capture stdout so the AI can read print() output
                    old_stdout = sys.stdout
                    sys.stdout = captured = io.StringIO()
                    try:
                        exec(script, {"__builtins__": __builtins__, "bpy": bpy})
                        output = captured.getvalue()
                        result_queue.put({"status": "success", "output": output if output else "Script executed successfully."})
                    except Exception as e:
                        output = captured.getvalue()
                        result_queue.put({
                            "status": "error",
                            "message": str(e),
                            "traceback": tb.format_exc(),
                            "output": output
                        })
                    finally:
                        sys.stdout = old_stdout

                elif action == "rename_object":
                    old_name = command.get("old_name")
                    new_name = command.get("new_name")
                    if old_name in bpy.data.objects:
                        bpy.data.objects[old_name].name = new_name
                        result_queue.put({"status": "success"})
                    else:
                        result_queue.put({"status": "error", "message": f"Object '{old_name}' not found."})

                elif action == "create_primitive":
                    prim_type = command.get("type", "CUBE").upper()
                    loc = command.get("location", [0, 0, 0])
                    size = command.get("size", 2.0)
                    name = command.get("name", None)
                    ops_map = {
                        "CUBE":     lambda: bpy.ops.mesh.primitive_cube_add(size=size, location=loc),
                        "SPHERE":   lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=size/2, location=loc),
                        "CYLINDER": lambda: bpy.ops.mesh.primitive_cylinder_add(radius=size/2, location=loc),
                        "PLANE":    lambda: bpy.ops.mesh.primitive_plane_add(size=size, location=loc),
                        "CONE":     lambda: bpy.ops.mesh.primitive_cone_add(radius1=size/2, location=loc),
                        "TORUS":    lambda: bpy.ops.mesh.primitive_torus_add(location=loc),
                        "MONKEY":   lambda: bpy.ops.mesh.primitive_monkey_add(size=size, location=loc),
                        "EMPTY":    lambda: bpy.ops.object.empty_add(location=loc),
                        "CAMERA":   lambda: bpy.ops.object.camera_add(location=loc),
                        "LIGHT":    lambda: bpy.ops.object.light_add(type="POINT", location=loc),
                    }
                    fn = ops_map.get(prim_type)
                    if fn:
                        fn()
                        obj = bpy.context.active_object
                        if name:
                            obj.name = name
                        result_queue.put({"status": "success", "name": obj.name})
                    else:
                        result_queue.put({"status": "error", "message": f"Unknown primitive type: {prim_type}. Use CUBE, SPHERE, CYLINDER, PLANE, CONE, TORUS, MONKEY, EMPTY, CAMERA, LIGHT."})

                elif action == "delete_object":
                    obj_name = command.get("name")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        bpy.data.objects.remove(obj, do_unlink=True)
                        result_queue.put({"status": "success"})
                    else:
                        result_queue.put({"status": "error", "message": f"Object '{obj_name}' not found."})

                elif action == "set_transform":
                    obj_name = command.get("name")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        if "location" in command:
                            obj.location = command["location"]
                        if "rotation" in command:
                            import math
                            rot = command["rotation"]
                            obj.rotation_euler = [math.radians(r) for r in rot]
                        if "scale" in command:
                            obj.scale = command["scale"]
                        result_queue.put({"status": "success"})
                    else:
                        result_queue.put({"status": "error", "message": f"Object '{obj_name}' not found."})

                elif action == "create_material":
                    mat_name = command.get("name", "NewMaterial")
                    color = command.get("color", [1.0, 1.0, 1.0, 1.0])  # RGBA 0-1
                    metallic = command.get("metallic", 0.0)
                    roughness = command.get("roughness", 0.5)
                    mat = bpy.data.materials.new(name=mat_name)
                    mat.use_nodes = True
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        bsdf.inputs["Base Color"].default_value = color
                        bsdf.inputs["Metallic"].default_value = metallic
                        bsdf.inputs["Roughness"].default_value = roughness
                    result_queue.put({"status": "success", "name": mat.name})

                elif action == "set_object_material":
                    obj_name = command.get("object")
                    mat_name = command.get("material")
                    if obj_name not in bpy.data.objects:
                        result_queue.put({"status": "error", "message": f"Object '{obj_name}' not found."})
                    elif mat_name not in bpy.data.materials:
                        result_queue.put({"status": "error", "message": f"Material '{mat_name}' not found. Create it first."})
                    else:
                        obj = bpy.data.objects[obj_name]
                        mat = bpy.data.materials[mat_name]
                        if obj.data.materials:
                            obj.data.materials[0] = mat
                        else:
                            obj.data.materials.append(mat)
                        result_queue.put({"status": "success"})

                elif action == "get_object_info":
                    obj_name = command.get("name")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        import math
                        info = {
                            "name": obj.name,
                            "type": obj.type,
                            "location": list(obj.location),
                            "rotation_euler_deg": [math.degrees(r) for r in obj.rotation_euler],
                            "scale": list(obj.scale),
                            "materials": [m.name for m in obj.data.materials] if hasattr(obj.data, "materials") else [],
                            "visible": obj.visible_get(),
                        }
                        result_queue.put({"status": "success", "data": info})
                    else:
                        result_queue.put({"status": "error", "message": f"Object '{obj_name}' not found."})

                elif action == "set_keyframe":
                    obj_name = command.get("name")
                    frame = command.get("frame", 1)
                    data_path = command.get("data_path", "location")  # location, rotation_euler, scale
                    bpy.context.scene.frame_set(frame)
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        obj.keyframe_insert(data_path=data_path, frame=frame)
                        result_queue.put({"status": "success"})
                    else:
                        result_queue.put({"status": "error", "message": f"Object '{obj_name}' not found."})

                elif action == "set_timeline":
                    start = command.get("start", 1)
                    end = command.get("end", 250)
                    fps = command.get("fps", 24)
                    bpy.context.scene.frame_start = start
                    bpy.context.scene.frame_end = end
                    bpy.context.scene.render.fps = fps
                    result_queue.put({"status": "success"})

                elif action == "render_frame":
                    output_path = command.get("output_path", "//render_output.png")
                    frame = command.get("frame", bpy.context.scene.frame_current)
                    bpy.context.scene.frame_set(frame)
                    bpy.context.scene.render.filepath = output_path
                    bpy.ops.render.render(write_still=True)
                    result_queue.put({"status": "success", "output": output_path})

                elif action == "set_render_settings":
                    res_x = command.get("resolution_x", None)
                    res_y = command.get("resolution_y", None)
                    engine = command.get("engine", None)  # CYCLES, BLENDER_EEVEE
                    samples = command.get("samples", None)
                    if res_x: bpy.context.scene.render.resolution_x = res_x
                    if res_y: bpy.context.scene.render.resolution_y = res_y
                    if engine: bpy.context.scene.render.engine = engine
                    if samples:
                        if bpy.context.scene.render.engine == "CYCLES":
                            bpy.context.scene.cycles.samples = samples
                        else:
                            bpy.context.scene.eevee.taa_render_samples = samples
                    result_queue.put({"status": "success"})

                elif action == "add_light":
                    light_type = command.get("light_type", "POINT").upper()  # POINT, SUN, SPOT, AREA
                    loc = command.get("location", [0, 0, 5])
                    energy = command.get("energy", 1000.0)
                    color = command.get("color", [1.0, 1.0, 1.0])
                    name = command.get("name", f"{light_type.capitalize()}Light")
                    bpy.ops.object.light_add(type=light_type, location=loc)
                    light_obj = bpy.context.active_object
                    light_obj.name = name
                    light_obj.data.energy = energy
                    light_obj.data.energy = energy
                    light_obj.data.color = color[:3]
                    result_queue.put({"status": "success", "name": light_obj.name})

                elif action == "take_screenshot":
                    try:
                        from .utils import get_sync_dir
                        sync_dir = get_sync_dir(bpy.context)
                        
                        # Route to Google Drive if configured
                        target_dir = sync_dir
                        addon = bpy.context.preferences.addons.get("blender_addon")
                        if addon and hasattr(addon.preferences, "google_drives") and len(addon.preferences.google_drives) > 0:
                            gdrive_path = addon.preferences.google_drives[0].path
                            if gdrive_path and os.path.isdir(gdrive_path):
                                target_dir = gdrive_path
                        elif addon and getattr(addon.preferences, "gdrive_1_meshes", ""):
                            if os.path.isdir(addon.preferences.gdrive_1_meshes):
                                target_dir = addon.preferences.gdrive_1_meshes

                        if not target_dir:
                            result_queue.put({"status": "error", "message": "No Sync folder or Google Drive configured."})
                        else:
                            import os
                            shot_path = os.path.join(target_dir, "blender_screenshot.png")
                            # Try viewport screenshot first
                            try:
                                # We temporarily override filepath to force the screenshot location
                                bpy.ops.screen.screenshot(filepath=shot_path, full=False)
                            except Exception:
                                # Fallback: OpenGL viewport render (failsafe)
                                old_path = bpy.context.scene.render.filepath
                                bpy.context.scene.render.filepath = shot_path
                                bpy.ops.render.opengl(write_still=True)
                                bpy.context.scene.render.filepath = old_path
                            
                            if os.path.exists(shot_path):
                                 import base64
                                 try:
                                     # Load the shot into Blender to resize/compress it
                                     img = bpy.data.images.load(shot_path)
                                     width, height = img.size[0], img.size[1]
                                     
                                     # Scale down to a max dimension of 1024px to reduce size
                                     max_dim = 1024
                                     if width > max_dim or height > max_dim:
                                         ratio = max_dim / max(width, height)
                                         new_w = int(width * ratio)
                                         new_h = int(height * ratio)
                                         img.scale(new_w, new_h)
                                     
                                     # Save as a compressed JPEG
                                     jpeg_path = shot_path.replace(".png", ".jpg")
                                     
                                     # Store old settings
                                     settings = bpy.context.scene.render.image_settings
                                     old_format = settings.file_format
                                     old_quality = settings.quality
                                     
                                     # Set to compressed JPEG
                                     settings.file_format = 'JPEG'
                                     settings.quality = 70
                                     
                                     # Save the image
                                     img.filepath_raw = jpeg_path
                                     img.save()
                                     
                                     # Restore settings
                                     settings.file_format = old_format
                                     settings.quality = old_quality
                                     
                                     # Clean up Blender image data block
                                     bpy.data.images.remove(img)
                                     
                                     result_queue.put({
                                         "status": "success",
                                         "filepath": jpeg_path
                                     })
                                 except Exception as e:
                                     result_queue.put({"status": "error", "message": f"Failed to compress screenshot: {str(e)}"})
                            else:
                                result_queue.put({"status": "error", "message": "Failed to generate screenshot file."})
                    except Exception as e:
                        result_queue.put({"status": "error", "message": f"Screenshot failed: {str(e)}"})

                elif action == "run_auto_rig":
                    # AI tells us which mesh to rig and optionally which armature to use
                    mesh_name = command.get("mesh", "")
                    armature_name = command.get("armature", "")
                    if mesh_name not in bpy.data.objects:
                        result_queue.put({"status": "error", "message": f"Mesh '{mesh_name}' not found."})
                    else:
                        mesh_obj = bpy.data.objects[mesh_name]
                        arm_obj = None
                        if armature_name and armature_name in bpy.data.objects:
                            arm_obj = bpy.data.objects[armature_name]
                        elif not armature_name:
                            # Find the first armature in the scene
                            for o in bpy.context.scene.objects:
                                if o.type == 'ARMATURE':
                                    arm_obj = o
                                    break
                        if not arm_obj:
                            result_queue.put({"status": "error", "message": "No armature found. Create or specify one."})
                        else:
                            # Parent mesh to armature with automatic weights
                            bpy.ops.object.select_all(action='DESELECT')
                            mesh_obj.select_set(True)
                            arm_obj.select_set(True)
                            bpy.context.view_layer.objects.active = arm_obj
                            try:
                                bpy.ops.object.parent_set(type='ARMATURE_AUTO')
                                result_queue.put({"status": "success", "message": f"Rigged '{mesh_name}' to '{arm_obj.name}' with automatic weights."})
                            except Exception as e:
                                result_queue.put({"status": "error", "message": f"Auto-rig failed: {str(e)}"})

                elif action == "apply_animation_to_character":
                    filepath = command.get("filepath", "")
                    target_object = command.get("target_object", "")
                    
                    if not filepath:
                        result_queue.put({"status": "error", "message": "No filepath provided"})
                    else:
                        try:
                            if target_object in bpy.data.objects:
                                obj = bpy.data.objects[target_object]
                                bpy.context.view_layer.objects.active = obj
                                obj.select_set(True)
                            
                            ext = filepath.lower().split('.')[-1]
                            if ext == "fbx":
                                bpy.ops.import_scene.fbx(filepath=filepath)
                            elif ext == "bvh":
                                bpy.ops.import_anim.bvh(filepath=filepath)
                            else:
                                result_queue.put({"status": "error", "message": f"Unsupported extension {ext}"})
                                continue
                            
                            result_queue.put({"status": "success", "message": f"Imported animation from {filepath}"})
                        except Exception as e:
                            result_queue.put({"status": "error", "message": str(e)})

                elif action == "generate_retarget_map":
                    # AI provides a custom bone mapping dict and a path
                    bone_map = command.get("bone_map", {})
                    output_path = command.get("output_path", "")
                    if not bone_map:
                        result_queue.put({"status": "error", "message": "No bone_map provided."})
                    else:
                        import os
                        if not output_path:
                            # Use route_asset for rig mapping
                            from .utils import route_asset
                            output_path = route_asset("animation", "ai_retarget.json", bpy.context)
                        data = {
                            "source": command.get("source_rig", "custom"),
                            "target": command.get("target_rig", "UE5_Mannequin"),
                            "bone_mapping": bone_map
                        }
                        with open(output_path, 'w') as f:
                            import json as _json
                            _json.dump(data, f, indent=2)
                        result_queue.put({"status": "success", "path": output_path, "mapping_count": len(bone_map)})

                elif action == "get_bone_hierarchy":
                    # AI reads the bone hierarchy of an armature for analysis
                    armature_name = command.get("armature", "")
                    arm_obj = None
                    if armature_name and armature_name in bpy.data.objects:
                        arm_obj = bpy.data.objects[armature_name]
                    else:
                        for o in bpy.context.scene.objects:
                            if o.type == 'ARMATURE':
                                arm_obj = o
                                break
                    if not arm_obj or arm_obj.type != 'ARMATURE':
                        result_queue.put({"status": "error", "message": "No armature found."})
                    else:
                        bones = []
                        for bone in arm_obj.data.bones:
                            bones.append({
                                "name": bone.name,
                                "parent": bone.parent.name if bone.parent else None,
                                "head": list(bone.head_local),
                                "tail": list(bone.tail_local),
                                "length": bone.length,
                                "children": [c.name for c in bone.children]
                            })
                        result_queue.put({"status": "success", "armature": arm_obj.name, "bone_count": len(bones), "bones": bones})

                elif action == "batch_create_blockout":
                    # AI creates a full blockout layout in one call
                    primitives = command.get("primitives", [])
                    created = []
                    for prim in primitives:
                        prim_type = prim.get("type", "CUBE").upper()
                        loc = prim.get("location", [0, 0, 0])
                        scl = prim.get("scale", [1, 1, 1])
                        rot = prim.get("rotation", [0, 0, 0])
                        size = prim.get("size", 2.0)
                        name = prim.get("name", None)
                        ops_map = {
                            "CUBE":     lambda s=size, l=loc: bpy.ops.mesh.primitive_cube_add(size=s, location=l),
                            "SPHERE":   lambda s=size, l=loc: bpy.ops.mesh.primitive_uv_sphere_add(radius=s/2, location=l),
                            "CYLINDER": lambda s=size, l=loc: bpy.ops.mesh.primitive_cylinder_add(radius=s/2, location=l),
                            "PLANE":    lambda s=size, l=loc: bpy.ops.mesh.primitive_plane_add(size=s, location=l),
                            "CONE":     lambda s=size, l=loc: bpy.ops.mesh.primitive_cone_add(radius1=s/2, location=l),
                        }
                        fn = ops_map.get(prim_type)
                        if fn:
                            fn()
                            obj = bpy.context.active_object
                            if name:
                                obj.name = name
                            import math
                            obj.scale = scl
                            obj.rotation_euler = [math.radians(r) for r in rot]
                            created.append(obj.name)
                    result_queue.put({"status": "success", "created": created, "count": len(created)})


                elif action == "create_geometry_nodes_modifier":
                    obj_name = command.get("name")
                    group_name = command.get("group_name", "GeometryNodes")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        group = bpy.data.node_groups.new(name=group_name, type='GeometryNodeTree')
                        group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
                        group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
                        input_node = group.nodes.new('NodeGroupInput')
                        output_node = group.nodes.new('NodeGroupOutput')
                        input_node.location = (-300, 0)
                        output_node.location = (300, 0)
                        group.links.new(input_node.outputs[0], output_node.inputs[0])
                        mod = obj.modifiers.new(name=group_name, type='NODES')
                        mod.node_group = group
                        result_queue.put({"status": "success", "modifier": mod.name, "node_group": group.name})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found: {obj_name}"})

                elif action == "add_geometry_node":
                    group_name = command.get("group_name")
                    node_type = command.get("node_type")
                    new_name = command.get("node_name", node_type)
                    if group_name in bpy.data.node_groups:
                        group = bpy.data.node_groups[group_name]
                        node = group.nodes.new(type=node_type)
                        node.name = new_name
                        node.location = (command.get("location_x", 0), command.get("location_y", 0))
                        result_queue.put({"status": "success", "node": node.name, "type": node.bl_idname})
                    else:
                        result_queue.put({"status": "error", "message": f"Node group not found: {group_name}"})

                elif action == "link_geometry_nodes":
                    group_name = command.get("group_name")
                    if group_name in bpy.data.node_groups:
                        group = bpy.data.node_groups[group_name]
                        from_node = group.nodes.get(command.get("from_node"))
                        to_node = group.nodes.get(command.get("to_node"))
                        if from_node and to_node:
                            from_idx = command.get("from_socket", 0)
                            to_idx = command.get("to_socket", 0)
                            link = group.links.new(from_node.outputs[from_idx], to_node.inputs[to_idx])
                            result_queue.put({"status": "success", "link": f"{from_node.name} -> {to_node.name}"})
                        else:
                            result_queue.put({"status": "error", "message": "Node not found"})
                    else:
                        result_queue.put({"status": "error", "message": f"Group not found: {group_name}"})

                elif action == "set_geometry_node_value":
                    group_name = command.get("group_name")
                    node_name = command.get("node_name")
                    if group_name in bpy.data.node_groups:
                        group = bpy.data.node_groups[group_name]
                        node = group.nodes.get(node_name)
                        if node:
                            sock_idx = command.get("socket_index", 0)
                            node.inputs[sock_idx].default_value = command.get("value")
                            result_queue.put({"status": "success"})
                        else:
                            result_queue.put({"status": "error", "message": "Node not found"})
                    else:
                        result_queue.put({"status": "error", "message": "Group not found"})

                elif action == "list_geometry_nodes":
                    group_name = command.get("group_name")
                    if group_name in bpy.data.node_groups:
                        group = bpy.data.node_groups[group_name]
                        nodes_info = [{"name": n.name, "type": n.bl_idname, "location": [n.location.x, n.location.y]} for n in group.nodes]
                        result_queue.put({"status": "success", "group": group_name, "nodes": nodes_info, "link_count": len(group.links)})
                    else:
                        result_queue.put({"status": "error", "message": f"Group not found: {group_name}"})

                elif action == "add_modifier":
                    obj_name = command.get("name")
                    mod_type = command.get("modifier_type", "SUBSURF").upper()
                    mod_name = command.get("modifier_name", mod_type.capitalize())
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        mod = obj.modifiers.new(name=mod_name, type=mod_type)
                        result_queue.put({"status": "success", "modifier": mod.name, "type": mod_type})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found: {obj_name}"})

                elif action == "remove_modifier":
                    obj_name = command.get("name")
                    mod_name = command.get("modifier_name")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        mod = obj.modifiers.get(mod_name)
                        if mod:
                            obj.modifiers.remove(mod)
                            result_queue.put({"status": "success"})
                        else:
                            result_queue.put({"status": "error", "message": f"Modifier '{mod_name}' not found"})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found: {obj_name}"})

                elif action == "apply_modifier":
                    obj_name = command.get("name")
                    mod_name = command.get("modifier_name")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.object.modifier_apply(modifier=mod_name)
                        result_queue.put({"status": "success"})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found: {obj_name}"})

                elif action == "set_modifier_property":
                    obj_name = command.get("name")
                    mod_name = command.get("modifier_name")
                    prop = command.get("property_name")
                    val = command.get("value")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        mod = obj.modifiers.get(mod_name)
                        if mod and hasattr(mod, prop):
                            setattr(mod, prop, val)
                            result_queue.put({"status": "success"})
                        else:
                            result_queue.put({"status": "error", "message": "Modifier or property not found"})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                elif action == "list_modifiers":
                    obj_name = command.get("name")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        mods = [{"name": m.name, "type": m.type, "show_viewport": m.show_viewport} for m in obj.modifiers]
                        result_queue.put({"status": "success", "object": obj_name, "modifiers": mods})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                elif action == "uv_unwrap":
                    obj_name = command.get("name")
                    method = command.get("method", "smart").lower()
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        bpy.ops.object.select_all(action='DESELECT')
                        obj.select_set(True)
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.object.mode_set(mode='EDIT')
                        bpy.ops.mesh.select_all(action='SELECT')
                        if method == "smart":
                            bpy.ops.uv.smart_project()
                        elif method == "cube":
                            bpy.ops.uv.cube_project()
                        elif method == "sphere":
                            bpy.ops.uv.sphere_project()
                        elif method == "cylinder":
                            bpy.ops.uv.cylinder_project()
                        else:
                            bpy.ops.uv.unwrap()
                        bpy.ops.object.mode_set(mode='OBJECT')
                        result_queue.put({"status": "success", "method": method})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found: {obj_name}"})

                elif action == "pack_uv_islands":
                    obj_name = command.get("name")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.object.mode_set(mode='EDIT')
                        bpy.ops.mesh.select_all(action='SELECT')
                        bpy.ops.uv.select_all(action='SELECT')
                        bpy.ops.uv.pack_islands()
                        bpy.ops.object.mode_set(mode='OBJECT')
                        result_queue.put({"status": "success"})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                elif action == "create_image_texture":
                    img_name = command.get("image_name", "NewImage")
                    width = command.get("width", 1024)
                    height = command.get("height", 1024)
                    color = command.get("color", [0.0, 0.0, 0.0, 1.0])
                    img = bpy.data.images.new(name=img_name, width=width, height=height)
                    img.generated_color = color
                    result_queue.put({"status": "success", "image": img.name, "size": [img.size[0], img.size[1]]})

                elif action == "save_image":
                    img_name = command.get("image_name")
                    filepath = command.get("filepath")
                    if img_name in bpy.data.images:
                        img = bpy.data.images[img_name]
                        img.filepath_raw = filepath
                        img.save()
                        result_queue.put({"status": "success", "saved_to": filepath})
                    else:
                        result_queue.put({"status": "error", "message": f"Image '{img_name}' not found"})

                elif action == "add_shader_node":
                    mat_name = command.get("material_name")
                    if mat_name in bpy.data.materials:
                        mat = bpy.data.materials[mat_name]
                        mat.use_nodes = True
                        node = mat.node_tree.nodes.new(type=command.get("node_type"))
                        node.name = command.get("node_name", node.bl_idname)
                        node.location = (command.get("location_x", 0), command.get("location_y", 0))
                        result_queue.put({"status": "success", "node": node.name, "type": node.bl_idname})
                    else:
                        result_queue.put({"status": "error", "message": f"Material not found: {mat_name}"})

                elif action == "link_shader_nodes":
                    mat_name = command.get("material_name")
                    if mat_name in bpy.data.materials:
                        mat = bpy.data.materials[mat_name]
                        mat.use_nodes = True
                        tree = mat.node_tree
                        from_node = tree.nodes.get(command.get("from_node"))
                        to_node = tree.nodes.get(command.get("to_node"))
                        if from_node and to_node:
                            from_idx = command.get("from_socket", 0)
                            to_idx = command.get("to_socket", 0)
                            tree.links.new(from_node.outputs[from_idx], to_node.inputs[to_idx])
                            result_queue.put({"status": "success", "link": f"{from_node.name} -> {to_node.name}"})
                        else:
                            result_queue.put({"status": "error", "message": "Nodes not found"})
                    else:
                        result_queue.put({"status": "error", "message": f"Material not found"})

                elif action == "set_shader_node_value":
                    mat_name = command.get("material_name")
                    if mat_name in bpy.data.materials:
                        mat = bpy.data.materials[mat_name]
                        mat.use_nodes = True
                        node = mat.node_tree.nodes.get(command.get("node_name"))
                        if node:
                            sock_idx = command.get("socket_index", 0)
                            val = command.get("value")
                            try:
                                if isinstance(val, list):
                                    node.inputs[sock_idx].default_value = val
                                else:
                                    node.inputs[sock_idx].default_value = val
                                result_queue.put({"status": "success"})
                            except Exception as e:
                                result_queue.put({"status": "error", "message": str(e)})
                        else:
                            result_queue.put({"status": "error", "message": "Node not found"})
                    else:
                        result_queue.put({"status": "error", "message": "Material not found"})

                elif action == "create_full_pbr_material":
                    mat_name = command.get("material_name", "NewPBRMaterial")
                    base_color = command.get("base_color", [0.8, 0.8, 0.8, 1.0])
                    metallic = command.get("metallic", 0.0)
                    roughness = command.get("roughness", 0.5)
                    emission_strength = command.get("emission_strength", 0.0)
                    mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(name=mat_name)
                    mat.use_nodes = True
                    nodes = mat.node_tree.nodes
                    links = mat.node_tree.links
                    nodes.clear()
                    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
                    bsdf.location = (0, 0)
                    bsdf.inputs['Base Color'].default_value = base_color
                    bsdf.inputs['Metallic'].default_value = metallic
                    bsdf.inputs['Roughness'].default_value = roughness
                    bsdf.inputs['Emission Strength'].default_value = emission_strength
                    output = nodes.new('ShaderNodeOutputMaterial')
                    output.location = (400, 0)
                    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
                    result_queue.put({"status": "success", "material": mat.name})

                elif action == "get_material_nodes":
                    mat_name = command.get("material_name")
                    if mat_name in bpy.data.materials:
                        mat = bpy.data.materials[mat_name]
                        if mat.use_nodes:
                            nodes_info = [{"name": n.name, "type": n.bl_idname, "location": [n.location.x, n.location.y]} for n in mat.node_tree.nodes]
                            result_queue.put({"status": "success", "material": mat_name, "nodes": nodes_info})
                        else:
                            result_queue.put({"status": "error", "message": "Material does not use nodes"})
                    else:
                        result_queue.put({"status": "error", "message": f"Material not found"})

                elif action == "export_fbx":
                    import os
                    filepath = command.get("filepath")
                    if not filepath:
                        from .utils import route_asset
                        filepath = route_asset("mesh", "blender_export.fbx", bpy.context)
                    selected_only = command.get("selected_only", False)
                    scale = command.get("scale_factor", 1.0)
                    bpy.ops.export_scene.fbx(
                        filepath=filepath,
                        use_selection=selected_only,
                        apply_unit_scale=True,
                        global_scale=scale,
                        bake_anim=True
                    )
                    result_queue.put({"status": "success", "exported_to": filepath})

                elif action == "export_gltf":
                    import os
                    filepath = command.get("filepath")
                    if not filepath:
                        from .utils import route_asset
                        filepath = route_asset("mesh", "blender_export.glb", bpy.context)
                    export_format = command.get("format", "GLB")
                    selected_only = command.get("selected_only", False)
                    bpy.ops.export_scene.gltf(
                        filepath=filepath,
                        export_format=export_format,
                        use_selection=selected_only,
                        export_apply=True
                    )
                    result_queue.put({"status": "success", "exported_to": filepath})

                elif action == "export_obj":
                    import os
                    filepath = command.get("filepath")
                    if not filepath:
                        from .utils import route_asset
                        filepath = route_asset("mesh", "blender_export.obj", bpy.context)
                    selected_only = command.get("selected_only", False)
                    try:
                        # Blender 4.x uses new OBJ exporter
                        bpy.ops.wm.obj_export(
                            filepath=filepath,
                            export_selected_objects=selected_only,
                            apply_modifiers=True
                        )
                    except AttributeError:
                        bpy.ops.export_scene.obj(filepath=filepath, use_selection=selected_only)
                    result_queue.put({"status": "success", "exported_to": filepath})

                elif action == "import_obj":
                    filepath = command.get("filepath")
                    try:
                        bpy.ops.wm.obj_import(filepath=filepath)
                    except AttributeError:
                        bpy.ops.import_scene.obj(filepath=filepath)
                    result_queue.put({"status": "success", "imported": filepath})

                elif action == "import_gltf":
                    filepath = command.get("filepath")
                    bpy.ops.import_scene.gltf(filepath=filepath)
                    result_queue.put({"status": "success", "imported": filepath})

                elif action == "export_alembic":
                    import os
                    filepath = command.get("filepath")
                    if not filepath:
                        from .utils import route_asset
                        filepath = route_asset("animation", "export.abc", bpy.context)
                    start = command.get("start_frame", bpy.context.scene.frame_start)
                    end = command.get("end_frame", bpy.context.scene.frame_end)
                    bpy.ops.wm.alembic_export(
                        filepath=filepath,
                        start=start,
                        end=end,
                        flatten=False
                    )
                    result_queue.put({"status": "success", "exported_to": filepath})

                elif action == "create_action":
                    obj_name = command.get("name")
                    action_name = command.get("action_name", "NewAction")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        anim_action = bpy.data.actions.new(name=action_name)
                        if not obj.animation_data:
                            obj.animation_data_create()
                        obj.animation_data.action = anim_action
                        result_queue.put({"status": "success", "action": anim_action.name})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                elif action == "push_to_nla":
                    obj_name = command.get("name")
                    track_name = command.get("track_name", "NLATrack")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        if obj.animation_data and obj.animation_data.action:
                            track = obj.animation_data.nla_tracks.new()
                            track.name = track_name
                            anim_action = obj.animation_data.action
                            strip = track.strips.new(anim_action.name, start=int(anim_action.frame_range[0]), action=anim_action)
                            obj.animation_data.action = None
                            result_queue.put({"status": "success", "track": track.name, "strip": strip.name})
                        else:
                            result_queue.put({"status": "error", "message": "No active action on object"})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                elif action == "clear_animation":
                    obj_name = command.get("name")
                    if obj_name in bpy.data.objects:
                        bpy.data.objects[obj_name].animation_data_clear()
                        result_queue.put({"status": "success", "cleared": obj_name})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                elif action == "set_bone_pose_rotation":
                    import math, mathutils
                    arm_name = command.get("armature_name")
                    bone_name = command.get("bone_name")
                    mode = command.get("rotation_mode", "QUATERNION")
                    values = command.get("values", [1, 0, 0, 0])
                    if arm_name in bpy.data.objects:
                        arm_obj = bpy.data.objects[arm_name]
                        if arm_obj.type == 'ARMATURE':
                            bpy.context.view_layer.objects.active = arm_obj
                            bpy.ops.object.mode_set(mode='POSE')
                            bone = arm_obj.pose.bones.get(bone_name)
                            if bone:
                                bone.rotation_mode = mode
                                if mode == 'QUATERNION':
                                    bone.rotation_quaternion = mathutils.Quaternion(values)
                                else:
                                    bone.rotation_euler = [math.radians(v) for v in values]
                                result_queue.put({"status": "success"})
                            else:
                                result_queue.put({"status": "error", "message": f"Bone '{bone_name}' not found"})
                            bpy.ops.object.mode_set(mode='OBJECT')
                        else:
                            result_queue.put({"status": "error", "message": "Not an armature"})
                    else:
                        result_queue.put({"status": "error", "message": "Object not found"})

                elif action == "add_rigid_body":
                    obj_name = command.get("name")
                    rb_type = command.get("rb_type", "ACTIVE")
                    mass = command.get("mass", 1.0)
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        bpy.context.view_layer.objects.active = obj
                        obj.select_set(True)
                        bpy.ops.rigidbody.object_add()
                        obj.rigid_body.type = rb_type
                        obj.rigid_body.mass = mass
                        result_queue.put({"status": "success", "type": rb_type, "mass": mass})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                elif action == "add_cloth_simulation":
                    obj_name = command.get("name")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.object.modifier_add(type='CLOTH')
                        result_queue.put({"status": "success", "object": obj_name})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                elif action == "add_particle_system":
                    obj_name = command.get("name")
                    particle_type = command.get("particle_type", "EMITTER")
                    count = command.get("count", 1000)
                    lifetime = command.get("lifetime", 50)
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.object.particle_system_add()
                        ps = obj.particle_systems[-1]
                        settings = ps.settings
                        settings.type = particle_type
                        settings.count = count
                        if particle_type == 'EMITTER':
                            settings.lifetime = lifetime
                        result_queue.put({"status": "success", "particle_system": ps.name, "type": particle_type})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                elif action == "bake_physics":
                    try:
                        bpy.ops.ptcache.bake_all(bake=True)
                        result_queue.put({"status": "success", "message": "Physics baked for all caches"})
                    except Exception as e:
                        result_queue.put({"status": "error", "message": str(e)})

                elif action == "setup_compositor":
                    bpy.context.scene.use_nodes = True
                    tree = bpy.context.scene.node_tree
                    nodes = tree.nodes
                    links = tree.links
                    nodes.clear()
                    rl = nodes.new('CompositorNodeRLayers')
                    rl.location = (-300, 0)
                    output = nodes.new('CompositorNodeOutputFile')
                    output.location = (300, 0)
                    output.base_path = command.get("output_path", "//compositor_output/")
                    links.new(rl.outputs['Image'], output.inputs[0])
                    result_queue.put({"status": "success", "output_path": output.base_path})

                elif action == "add_compositor_node":
                    bpy.context.scene.use_nodes = True
                    tree = bpy.context.scene.node_tree
                    node = tree.nodes.new(type=command.get("node_type"))
                    node.name = command.get("node_name", node.bl_idname)
                    node.location = (command.get("location_x", 0), command.get("location_y", 0))
                    result_queue.put({"status": "success", "node": node.name, "type": node.bl_idname})

                elif action == "link_compositor_nodes":
                    tree = bpy.context.scene.node_tree
                    if tree:
                        from_node = tree.nodes.get(command.get("from_node"))
                        to_node = tree.nodes.get(command.get("to_node"))
                        if from_node and to_node:
                            tree.links.new(from_node.outputs[command.get("from_socket", 0)], to_node.inputs[command.get("to_socket", 0)])
                            result_queue.put({"status": "success", "link": f"{from_node.name} -> {to_node.name}"})
                        else:
                            result_queue.put({"status": "error", "message": "Nodes not found"})
                    else:
                        result_queue.put({"status": "error", "message": "Compositor not enabled"})

                elif action == "set_render_pass":
                    pass_name = command.get("pass_name", "ao").lower()
                    vl = bpy.context.view_layer
                    pass_map = {
                        "ao": "use_pass_ambient_occlusion",
                        "shadow": "use_pass_shadow",
                        "z": "use_pass_z",
                        "normal": "use_pass_normal",
                        "diffuse_direct": "use_pass_diffuse_direct",
                        "diffuse_indirect": "use_pass_diffuse_indirect",
                        "diffuse_color": "use_pass_diffuse_color",
                        "glossy_direct": "use_pass_glossy_direct",
                        "glossy_indirect": "use_pass_glossy_indirect",
                    }
                    attr = pass_map.get(pass_name)
                    if attr:
                        setattr(vl, attr, True)
                        result_queue.put({"status": "success", "pass": pass_name, "enabled": True})
                    else:
                        result_queue.put({"status": "error", "message": f"Unknown pass: {pass_name}"})

                elif action == "rename_object":
                    old = command.get("old_name")
                    new = command.get("new_name")
                    if old in bpy.data.objects:
                        bpy.data.objects[old].name = new
                        result_queue.put({"status": "success", "renamed_to": new})
                    else:
                        result_queue.put({"status": "error", "message": f"Object '{old}' not found"})

                elif action == "duplicate_object":
                    obj_name = command.get("name")
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        new_obj = obj.copy()
                        new_obj.data = obj.data.copy()
                        new_obj.name = command.get("new_name", obj_name + "_copy")
                        new_obj.location.x += command.get("offset_x", 0)
                        new_obj.location.y += command.get("offset_y", 0)
                        new_obj.location.z += command.get("offset_z", 0)
                        bpy.context.collection.objects.link(new_obj)
                        result_queue.put({"status": "success", "new_object": new_obj.name})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                elif action == "select_objects_by_type":
                    obj_type = command.get("object_type", "MESH").upper()
                    bpy.ops.object.select_all(action='DESELECT')
                    matches = [obj.name for obj in bpy.context.scene.objects if obj.type == obj_type]
                    for n in matches:
                        bpy.data.objects[n].select_set(True)
                    result_queue.put({"status": "success", "selected": matches, "count": len(matches)})

                elif action == "join_objects":
                    obj_names = command.get("object_names", [])
                    bpy.ops.object.select_all(action='DESELECT')
                    for n in obj_names:
                        if n in bpy.data.objects:
                            bpy.data.objects[n].select_set(True)
                    if bpy.context.selected_objects:
                        bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
                        bpy.ops.object.join()
                        result_name = command.get("result_name")
                        if result_name:
                            bpy.context.active_object.name = result_name
                        result_queue.put({"status": "success", "result": bpy.context.active_object.name})
                    else:
                        result_queue.put({"status": "error", "message": "No valid objects to join"})

                elif action == "set_origin":
                    obj_name = command.get("name")
                    origin_type = command.get("origin_type", "ORIGIN_CENTER_OF_MASS")
                    if obj_name in bpy.data.objects:
                        bpy.context.view_layer.objects.active = bpy.data.objects[obj_name]
                        bpy.ops.object.origin_set(type=origin_type)
                        result_queue.put({"status": "success", "origin_type": origin_type})
                    else:
                        result_queue.put({"status": "error", "message": f"Object not found"})

                else:

                    result_queue.put({"status": "error", "message": f"Unknown action: {action}"})
            except Exception as e:
                result_queue.put({"status": "error", "message": str(e)})
                
    except queue.Empty:
        pass
        
    return 0.1 # Run again in 0.1 seconds

def start_server():
    """Starts the background socket server."""
    global server_thread, is_running
    if is_running:
        return
        
    server_thread = threading.Thread(target=server_loop)
    server_thread.daemon = True
    server_thread.start()
    
    bpy.app.timers.register(process_execution_queue)

def stop_server():
    """Stops the background socket server."""
    global is_running, server_socket
    is_running = False
    if server_socket:
        # Connect to ourselves to break the accept() loop if it's waiting
        try:
            socket.create_connection(("127.0.0.1", 12345), timeout=1.0).close()
        except Exception:
            pass
    if bpy.app.timers.is_registered(process_execution_queue):
        bpy.app.timers.unregister(process_execution_queue)

class UBSyncAIBridgeOperator(bpy.types.Operator):
    bl_idname = "ubsync.ai_bridge"
    bl_label = "Toggle AI Bridge"
    bl_description = "Start or stop the local socket server that the MCP script connects to"

    def execute(self, context):
        settings = context.scene.ubsync_settings
        if not settings.enable_mcp:
            self.report({'WARNING'}, "AI MCP support is disabled in addon settings.")
            return {'CANCELLED'}

        if is_running:
            stop_server()
            self.report({'INFO'}, "AI Bridge stopped.")
        else:
            start_server()
            self.report({'INFO'}, "AI Bridge started on port 12345. Run mcp_server.py in terminal.")
            
        return {'FINISHED'}

def register():
    # Auto-start the AI Bridge server so Claude/MCP can connect immediately
    import bpy
    def _delayed_start():
        try:
            start_server()
            print("AI Bridge: Auto-started on port 12345")
        except Exception as e:
            print(f"AI Bridge: Auto-start failed: {e}")
        return None  # Don't repeat
    bpy.app.timers.register(_delayed_start, first_interval=2.0)

def unregister():
    stop_server()
