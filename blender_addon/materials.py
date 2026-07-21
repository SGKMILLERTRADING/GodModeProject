import bpy
import json
import os

def parse_principled_bsdf(material):
    """Extract parameters from a Principled BSDF node."""
    data = {
        "name": material.name,
        "base_color": [1.0, 1.0, 1.0, 1.0],
        "roughness": 0.5,
        "metallic": 0.0,
        "specular": 0.5,
        "base_color_texture": "",
        "normal_texture": "",
        "roughness_texture": "",
        "metallic_texture": ""
    }
    
    if not material.use_nodes:
        if hasattr(material, 'diffuse_color'):
            data["base_color"] = list(material.diffuse_color)
        return data

    bsdf = None
    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            bsdf = node
            break
            
    if not bsdf:
        return data

    def get_input_val(input_name, default_val):
        input_socket = bsdf.inputs.get(input_name)
        if not input_socket:
            return default_val
            
        if input_socket.is_linked:
            link = input_socket.links[0]
            if link.from_node.type == 'TEX_IMAGE':
                if link.from_node.image:
                    return link.from_node.image.filepath
        return input_socket.default_value

    # Get values or texture paths
    base_color_val = get_input_val("Base Color", data["base_color"])
    if isinstance(base_color_val, str):
        data["base_color_texture"] = bpy.path.abspath(base_color_val)
    else:
        data["base_color"] = list(base_color_val)

    roughness_val = get_input_val("Roughness", data["roughness"])
    if isinstance(roughness_val, str):
        data["roughness_texture"] = bpy.path.abspath(roughness_val)
    else:
        data["roughness"] = float(roughness_val)
        
    metallic_val = get_input_val("Metallic", data["metallic"])
    if isinstance(metallic_val, str):
        data["metallic_texture"] = bpy.path.abspath(metallic_val)
    else:
        data["metallic"] = float(metallic_val)
        
    normal_input = bsdf.inputs.get("Normal")
    if normal_input and normal_input.is_linked:
        normal_node = normal_input.links[0].from_node
        if normal_node.type == 'NORMAL_MAP' and normal_node.inputs["Color"].is_linked:
            tex_node = normal_node.inputs["Color"].links[0].from_node
            if tex_node.type == 'TEX_IMAGE' and tex_node.image:
                data["normal_texture"] = bpy.path.abspath(tex_node.image.filepath)

    return data

def export_materials_to_json(objects, filepath):
    """Exports material data for the given objects to a JSON file."""
    materials = {}
    for obj in objects:
        if obj.type == 'MESH':
            for slot in obj.material_slots:
                if slot.material and slot.material.name not in materials:
                    materials[slot.material.name] = parse_principled_bsdf(slot.material)
                    
    with open(filepath, 'w') as f:
        json.dump(materials, f, indent=4)
        
    return materials
