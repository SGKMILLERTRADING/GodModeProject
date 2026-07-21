bl_info = {
    "name": "Unreal-Blender Sync",
    "description": "Sync Blender assets and scenes with Unreal Engine, including FBX export, Google Drive support, and MCP integration.",
    "author": "Unreal-Blender Team",
    "version": (0, 1, 0),
    "blender": (5, 2, 0),
    "support": "COMMUNITY",
    "category": "3D View",
    "location": "View3D > Sidebar > Unreal-Blender",
    "warning": "",
}

import bpy

from .operators import (
    UBSyncExportToUnrealOperator,
    UBSyncImportFromUnrealOperator,
    UBSyncAutoWeightOperator,
    UBSyncRetargetOperator,
    UBSyncExportMeshOnlyOperator,
    UBSyncExportAnimOnlyOperator,
    UBSyncUninstallOperator,
)
from .hair import UBSyncExportHairOperator
from .panels import UBSyncPanel
from .preferences import (
    UBSyncSettings,
    UBSyncGoogleDriveEntry,
    UBSyncPreferences,
)
from .google_drive import (
    UBSyncSaveToGoogleDriveOperator,
    UBSyncLoadFromGoogleDriveOperator,
    UBSyncAddGoogleDriveOperator,
    UBSyncRemoveGoogleDriveOperator,
)
from .ai_bridge import UBSyncAIBridgeOperator, stop_server
from . import livelink

classes = (
    UBSyncSettings,
    UBSyncGoogleDriveEntry,
    UBSyncPreferences,
    UBSyncExportToUnrealOperator,
    UBSyncImportFromUnrealOperator,
    UBSyncAutoWeightOperator,
    UBSyncRetargetOperator,
    UBSyncExportMeshOnlyOperator,
    UBSyncExportAnimOnlyOperator,
    UBSyncExportHairOperator,
    UBSyncUninstallOperator,
    UBSyncSaveToGoogleDriveOperator,
    UBSyncLoadFromGoogleDriveOperator,
    UBSyncAddGoogleDriveOperator,
    UBSyncRemoveGoogleDriveOperator,
    UBSyncAIBridgeOperator,
    UBSyncPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.ubsync_settings = bpy.props.PointerProperty(type=UBSyncSettings)
    livelink.register()
    
    # Auto-start AI bridge socket server
    from . import ai_bridge
    ai_bridge.register()

def unregister():
    stop_server()

    if hasattr(bpy.types.Scene, "ubsync_settings"):
        del bpy.types.Scene.ubsync_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    livelink.unregister()

