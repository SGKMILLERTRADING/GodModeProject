import os
import bpy

def get_sync_dir(context):
    """Return the sync folder path for Unreal‑Blender communication.
    It first checks the ``sync_folder`` defined in the add‑on preferences.
    If that is empty, it falls back to constructing a path based on the
    ``default_unreal_project_path`` preference (Saved/BlenderSync).
    Returns an absolute path string or ``None`` if neither is set.
    """
    prefs = context.preferences.addons.get(__package__)
    if not prefs:
        return None
    addon_prefs = prefs.preferences
    sync_folder = getattr(addon_prefs, "sync_folder", "")
    if sync_folder and os.path.isdir(sync_folder):
        return os.path.abspath(sync_folder)
    # Fallback to default Unreal project path
    unreal_path = getattr(addon_prefs, "default_unreal_project_path", "")
    if unreal_path and os.path.isdir(unreal_path):
        return os.path.abspath(os.path.join(unreal_path, "Saved", "BlenderSync"))
    
    # Absolute default fallback to main project sync folder
    default_sync = r"C:\Users\sassy\OneDrive\Desktop\Unreal and Blender plugin and extension\SyncFolder"
    os.makedirs(default_sync, exist_ok=True)
    return default_sync

def get_prefs(context=None):
    if context is None:
        context = bpy.context
    prefs = context.preferences.addons.get(__package__)
    if prefs:
        return prefs.preferences
    return None

def get_dropbox_path(context=None):
    prefs = get_prefs(context)
    if prefs and getattr(prefs, "dropbox_path", ""):
        return os.path.abspath(prefs.dropbox_path)
    return ""

def get_asset_library_path(context=None):
    prefs = get_prefs(context)
    if prefs and getattr(prefs, "asset_library_path", ""):
        return os.path.abspath(prefs.asset_library_path)
    return ""

def get_gdrive_meshes_path(context=None):
    prefs = get_prefs(context)
    if prefs and getattr(prefs, "gdrive_1_meshes", ""):
        return os.path.abspath(prefs.gdrive_1_meshes)
    return ""

def get_gdrive_skins_path(context=None):
    prefs = get_prefs(context)
    if prefs and getattr(prefs, "gdrive_2_skins", ""):
        return os.path.abspath(prefs.gdrive_2_skins)
    return ""

def get_gdrive_anims_path(context=None):
    prefs = get_prefs(context)
    if prefs and getattr(prefs, "gdrive_3_anims", ""):
        return os.path.abspath(prefs.gdrive_3_anims)
    return ""

def get_gdrive_audio_path(context=None):
    prefs = get_prefs(context)
    if prefs and getattr(prefs, "gdrive_4_audio", ""):
        return os.path.abspath(prefs.gdrive_4_audio)
    return ""

def route_asset(asset_type, filename="", context=None):
    """
    asset_type should be 'mesh', 'skin', 'animation', or 'audio'.
    Returns the absolute directory where the file should be saved/exported.
    Also creates the directory if it does not exist.
    """
    target_dir = ""
    
    if asset_type == 'mesh':
        target_dir = get_gdrive_meshes_path(context)
    elif asset_type == 'skin':
        target_dir = get_gdrive_skins_path(context)
    elif asset_type == 'animation':
        target_dir = get_gdrive_anims_path(context)
    elif asset_type == 'audio':
        target_dir = get_gdrive_audio_path(context)
        
    if not target_dir:
        asset_lib = get_asset_library_path(context)
        if asset_lib:
            folder_map = {
                'mesh': 'meshes',
                'skin': 'skins',
                'animation': 'animations',
                'audio': 'audio'
            }
            subfolder = folder_map.get(asset_type, '')
            if subfolder:
                target_dir = os.path.join(asset_lib, subfolder)
            else:
                target_dir = asset_lib

    if not target_dir:
        base_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.expanduser("~")
        folder_map = {
            'mesh': 'meshes',
            'skin': 'skins',
            'animation': 'animations',
            'audio': 'audio'
        }
        subfolder = folder_map.get(asset_type, '')
        if subfolder:
            target_dir = os.path.join(base_dir, subfolder)
        else:
            target_dir = base_dir

    if target_dir:
        os.makedirs(target_dir, exist_ok=True)
        
    return os.path.join(target_dir, filename) if filename else target_dir
