import re
import json
import os

base_path = r'c:\Users\sassy\OneDrive\Desktop\Unreal and Blender plugin and extension'

# 1. ai_bridge.py
ai_bridge_path = os.path.join(base_path, 'blender_addon', 'ai_bridge.py')
with open(ai_bridge_path, 'r', encoding='utf-8') as f:
    ai_bridge_code = f.read()

ai_bridge_injections = """
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
                    filepath = command.get("filepath", os.path.join(os.path.expanduser("~"), "blender_export.fbx"))
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
                    filepath = command.get("filepath", os.path.join(os.path.expanduser("~"), "blender_export.glb"))
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
                    filepath = command.get("filepath", os.path.join(os.path.expanduser("~"), "blender_export.obj"))
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
                    filepath = command.get("filepath", os.path.join(os.path.expanduser("~"), "export.abc"))
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
"""

ai_bridge_target1 = '''                else:

                    result_queue.put({"status": "error", "message": f"Unknown action: {action}"})'''
ai_bridge_target2 = '''                else:
                    result_queue.put({"status": "error", "message": f"Unknown action: {action}"})'''

if ai_bridge_target1 in ai_bridge_code:
    ai_bridge_code = ai_bridge_code.replace(ai_bridge_target1, ai_bridge_injections + '\n' + ai_bridge_target1)
elif ai_bridge_target2 in ai_bridge_code:
    ai_bridge_code = ai_bridge_code.replace(ai_bridge_target2, ai_bridge_injections + '\n' + ai_bridge_target2)

with open(ai_bridge_path, 'w', encoding='utf-8') as f:
    f.write(ai_bridge_code)
print("Patched ai_bridge.py")


# 2. mcp_server.py
mcp_server_path = os.path.join(base_path, 'blender_addon', 'mcp_server.py')
with open(mcp_server_path, 'r', encoding='utf-8') as f:
    mcp_server_code = f.read()

mcp_server_injections = """
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
"""

mcp_server_code = mcp_server_code.replace("if __name__ == \"__main__\":", mcp_server_injections + "\nif __name__ == \"__main__\":")

with open(mcp_server_path, 'w', encoding='utf-8') as f:
    f.write(mcp_server_code)
print("Patched mcp_server.py")

# 3. blender_mcp_bridge.py
bridge_path = os.path.join(base_path, 'blender_mcp_bridge.py')
with open(bridge_path, 'r', encoding='utf-8') as f:
    bridge_code = f.read()

# Since we want to append to TOOLS array, let's just parse the file and insert it before the closing ']'
# The closing bracket of TOOLS array is just before "def call_blender"
# Let's find "def call_blender" and then walk back to the "]" 
def_call_index = bridge_code.find("def call_blender")
close_bracket_index = bridge_code.rfind("]", 0, def_call_index)

bridge_schemas = """    ,
    {
        "name": "create_geometry_nodes_modifier",
        "description": "Create a geometry nodes modifier on an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "group_name": {"type": "string", "default": "GeometryNodes"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "add_geometry_node",
        "description": "Add a node to a geometry node group.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"},
                "node_type": {"type": "string"},
                "node_name": {"type": "string"},
                "location_x": {"type": "number", "default": 0},
                "location_y": {"type": "number", "default": 0}
            },
            "required": ["group_name", "node_type"]
        }
    },
    {
        "name": "link_geometry_nodes",
        "description": "Link two geometry nodes together.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"},
                "from_node": {"type": "string"},
                "to_node": {"type": "string"},
                "from_socket": {"type": "integer", "default": 0},
                "to_socket": {"type": "integer", "default": 0}
            },
            "required": ["group_name", "from_node", "to_node"]
        }
    },
    {
        "name": "set_geometry_node_value",
        "description": "Set a value on a geometry node's input socket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"},
                "node_name": {"type": "string"},
                "value": {},
                "socket_index": {"type": "integer", "default": 0}
            },
            "required": ["group_name", "node_name", "value"]
        }
    },
    {
        "name": "list_geometry_nodes",
        "description": "List all nodes in a geometry node group.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"}
            },
            "required": ["group_name"]
        }
    },
    {
        "name": "add_modifier",
        "description": "Add a modifier to an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "modifier_type": {"type": "string", "default": "SUBSURF"},
                "modifier_name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "remove_modifier",
        "description": "Remove a modifier from an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "modifier_name": {"type": "string"}
            },
            "required": ["name", "modifier_name"]
        }
    },
    {
        "name": "apply_modifier",
        "description": "Apply a modifier on an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "modifier_name": {"type": "string"}
            },
            "required": ["name", "modifier_name"]
        }
    },
    {
        "name": "set_modifier_property",
        "description": "Set a property on a modifier.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "modifier_name": {"type": "string"},
                "property_name": {"type": "string"},
                "value": {}
            },
            "required": ["name", "modifier_name", "property_name", "value"]
        }
    },
    {
        "name": "list_modifiers",
        "description": "List modifiers on an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "uv_unwrap",
        "description": "UV Unwrap an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "method": {"type": "string", "default": "smart"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "pack_uv_islands",
        "description": "Pack UV islands for an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_image_texture",
        "description": "Create a new image texture in Blender.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_name": {"type": "string", "default": "NewImage"},
                "width": {"type": "integer", "default": 1024},
                "height": {"type": "integer", "default": 1024},
                "color": {"type": "array", "items": {"type": "number"}, "default": [0.0, 0.0, 0.0, 1.0]}
            }
        }
    },
    {
        "name": "save_image",
        "description": "Save an image texture to disk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_name": {"type": "string"},
                "filepath": {"type": "string"}
            },
            "required": ["image_name", "filepath"]
        }
    },
    {
        "name": "add_shader_node",
        "description": "Add a shader node to a material.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string"},
                "node_type": {"type": "string"},
                "node_name": {"type": "string"},
                "location_x": {"type": "number", "default": 0},
                "location_y": {"type": "number", "default": 0}
            },
            "required": ["material_name", "node_type"]
        }
    },
    {
        "name": "link_shader_nodes",
        "description": "Link shader nodes together.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string"},
                "from_node": {"type": "string"},
                "to_node": {"type": "string"},
                "from_socket": {"type": "integer", "default": 0},
                "to_socket": {"type": "integer", "default": 0}
            },
            "required": ["material_name", "from_node", "to_node"]
        }
    },
    {
        "name": "set_shader_node_value",
        "description": "Set a value on a shader node socket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string"},
                "node_name": {"type": "string"},
                "value": {},
                "socket_index": {"type": "integer", "default": 0}
            },
            "required": ["material_name", "node_name", "value"]
        }
    },
    {
        "name": "create_full_pbr_material",
        "description": "Create a full PBR material with standard inputs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string", "default": "NewPBRMaterial"},
                "base_color": {"type": "array", "items": {"type": "number"}, "default": [0.8, 0.8, 0.8, 1.0]},
                "metallic": {"type": "number", "default": 0.0},
                "roughness": {"type": "number", "default": 0.5},
                "emission_strength": {"type": "number", "default": 0.0}
            }
        }
    },
    {
        "name": "get_material_nodes",
        "description": "List all nodes in a material.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string"}
            },
            "required": ["material_name"]
        }
    },
    {
        "name": "export_fbx",
        "description": "Export the scene to FBX.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "selected_only": {"type": "boolean", "default": False},
                "scale_factor": {"type": "number", "default": 1.0}
            }
        }
    },
    {
        "name": "export_gltf",
        "description": "Export the scene to GLTF/GLB.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "format": {"type": "string", "default": "GLB"},
                "selected_only": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "name": "export_obj",
        "description": "Export the scene to OBJ.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "selected_only": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "name": "import_obj",
        "description": "Import an OBJ file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"}
            },
            "required": ["filepath"]
        }
    },
    {
        "name": "import_gltf",
        "description": "Import a GLTF/GLB file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"}
            },
            "required": ["filepath"]
        }
    },
    {
        "name": "export_alembic",
        "description": "Export the scene to Alembic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "start_frame": {"type": "integer"},
                "end_frame": {"type": "integer"}
            }
        }
    },
    {
        "name": "create_action",
        "description": "Create a new animation action for an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "action_name": {"type": "string", "default": "NewAction"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "push_to_nla",
        "description": "Push the active action to a new NLA track.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "track_name": {"type": "string", "default": "NLATrack"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "clear_animation",
        "description": "Clear all animation data from an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "set_bone_pose_rotation",
        "description": "Set a bone's pose rotation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "armature_name": {"type": "string"},
                "bone_name": {"type": "string"},
                "rotation_mode": {"type": "string", "default": "QUATERNION"},
                "values": {"type": "array", "items": {"type": "number"}, "default": [1, 0, 0, 0]}
            },
            "required": ["armature_name", "bone_name"]
        }
    },
    {
        "name": "add_rigid_body",
        "description": "Add a rigid body to an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "rb_type": {"type": "string", "default": "ACTIVE"},
                "mass": {"type": "number", "default": 1.0}
            },
            "required": ["name"]
        }
    },
    {
        "name": "add_cloth_simulation",
        "description": "Add cloth simulation to an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "add_particle_system",
        "description": "Add a particle system to an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "particle_type": {"type": "string", "default": "EMITTER"},
                "count": {"type": "integer", "default": 1000},
                "lifetime": {"type": "integer", "default": 50}
            },
            "required": ["name"]
        }
    },
    {
        "name": "bake_physics",
        "description": "Bake all physics caches.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "setup_compositor",
        "description": "Setup basic compositor nodes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "default": "//compositor_output/"}
            }
        }
    },
    {
        "name": "add_compositor_node",
        "description": "Add a compositor node.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_type": {"type": "string"},
                "node_name": {"type": "string"},
                "location_x": {"type": "number", "default": 0},
                "location_y": {"type": "number", "default": 0}
            },
            "required": ["node_type"]
        }
    },
    {
        "name": "link_compositor_nodes",
        "description": "Link two compositor nodes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_node": {"type": "string"},
                "to_node": {"type": "string"},
                "from_socket": {"type": "integer", "default": 0},
                "to_socket": {"type": "integer", "default": 0}
            },
            "required": ["from_node", "to_node"]
        }
    },
    {
        "name": "set_render_pass",
        "description": "Enable a specific render pass.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pass_name": {"type": "string", "default": "ao"}
            }
        }
    },
    {
        "name": "duplicate_object",
        "description": "Duplicate an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "new_name": {"type": "string"},
                "offset_x": {"type": "number", "default": 0},
                "offset_y": {"type": "number", "default": 0},
                "offset_z": {"type": "number", "default": 0}
            },
            "required": ["name"]
        }
    },
    {
        "name": "select_objects_by_type",
        "description": "Select objects by type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "object_type": {"type": "string", "default": "MESH"}
            }
        }
    },
    {
        "name": "join_objects",
        "description": "Join multiple objects into one.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "object_names": {"type": "array", "items": {"type": "string"}},
                "result_name": {"type": "string"}
            },
            "required": ["object_names"]
        }
    },
    {
        "name": "set_origin",
        "description": "Set the origin of an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "origin_type": {"type": "string", "default": "ORIGIN_CENTER_OF_MASS"}
            },
            "required": ["name"]
        }
    }
"""

bridge_code = bridge_code[:close_bracket_index] + bridge_schemas + bridge_code[close_bracket_index:]
with open(bridge_path, 'w', encoding='utf-8') as f:
    f.write(bridge_code)
print("Patched blender_mcp_bridge.py")
