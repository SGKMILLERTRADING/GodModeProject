import unreal
import json
import os

def process_imported_asset(asset_path):
    """
    Called after an FBX is imported into Unreal Engine.
    Checks for _materials.json and _retarget.json sidecar files.
    """
    # e.g., /Game/BlenderSync/MyMesh
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not asset:
        return
        
    system_path = unreal.SystemLibrary.get_system_path(asset)
    if not system_path:
        # It's an internal path, try to find the source FBX path from import data
        if hasattr(asset, 'asset_import_data') and asset.asset_import_data:
            filenames = asset.asset_import_data.extract_filenames()
            if filenames:
                system_path = filenames[0]
                
    if not system_path:
        unreal.log_warning(f"Could not determine source file path for {asset_path}")
        return

    base_path, _ = os.path.splitext(system_path)
    
    # 1. Process Materials
    mat_json_path = f"{base_path}_materials.json"
    if os.path.exists(mat_json_path):
        unreal.log(f"Found material JSON: {mat_json_path}")
        process_materials(asset, mat_json_path)
        
    # 2. Process Retargeting (if it's a skeletal mesh)
    retarget_json_path = f"{base_path}_retarget.json"
    if os.path.exists(retarget_json_path):
        if isinstance(asset, unreal.SkeletalMesh):
            unreal.log(f"Found retarget JSON: {retarget_json_path}")
            process_retargeting(asset, retarget_json_path)

def process_materials(mesh_asset, json_path):
    """Reads material JSON and creates Unreal Material Instances."""
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    asset_folder = unreal.Paths.get_path(mesh_asset.get_path_name())
    
    # We assume a master material exists at /Game/BlenderSync/M_Master_Blender
    # In a real pipeline, you would create this master material beforehand.
    master_mat_path = "/Game/BlenderSync/M_Master_Blender"
    master_mat = unreal.EditorAssetLibrary.load_asset(master_mat_path)
    
    if not master_mat:
        unreal.log_warning("Master material not found, skipping material creation.")
        return

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    
    for mat_name, props in data.items():
        mi_name = f"MI_{mat_name}"
        mi_path = f"{asset_folder}/{mi_name}"
        
        # Check if it already exists
        mi = unreal.EditorAssetLibrary.load_asset(mi_path)
        if not mi:
            # Create new Material Instance Constant
            mi_factory = unreal.MaterialInstanceConstantFactoryNew()
            mi = asset_tools.create_asset(mi_name, asset_folder, unreal.MaterialInstanceConstant, mi_factory)
            
            # Set parent
            unreal.MaterialEditingLibrary.set_material_instance_parent(mi, master_mat)
            
        # Set vector parameter for Base Color
        color = props.get("base_color", [1,1,1,1])
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
            mi, "BaseColor", unreal.LinearColor(color[0], color[1], color[2], color[3])
        )
        
        # Set scalar parameters
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Roughness", props.get("roughness", 0.5))
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Metallic", props.get("metallic", 0.0))
        
        # In a full implementation, we'd also import the textures from props["base_color_texture"] etc.
        # and assign them to texture parameters here.
        
        unreal.EditorAssetLibrary.save_asset(mi.get_path_name())

def process_retargeting(skeletal_mesh, json_path):
    """Reads retargeting JSON and creates an IKRig."""
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    mapping = data.get("bone_mapping", {})
    if not mapping:
        return
        
    # NOTE: Unreal 5 IKRig Python API is limited, but you can set up basic Retarget Chains
    # or create a mapping asset. For this MVP, we just log the mapping so the user 
    # or a C++ plugin extension can utilize it.
    unreal.log(f"Applying Retarget Mapping for {skeletal_mesh.get_name()}:")
    for src, dst in mapping.items():
        unreal.log(f"  {src} -> {dst}")
        
    # Example placeholder for IKRig creation logic
    unreal.log("IKRig creation requires C++ extension or manual setup in current Unreal Python API.")
