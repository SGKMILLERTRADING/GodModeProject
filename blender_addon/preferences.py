import bpy


# ---------------------------------------------------------------------------
# Per-Scene Settings (shown in the sidebar panel)
# ---------------------------------------------------------------------------
class UBSyncSettings(bpy.types.PropertyGroup):
    export_path: bpy.props.StringProperty(
        name="Export Path",
        description="Path to export FBX files for Unreal.",
        subtype='FILE_PATH',
        default=""
    )
    import_path: bpy.props.StringProperty(
        name="Import Path",
        description="Path to import Unreal FBX files.",
        subtype='FILE_PATH',
        default=""
    )
    sync_format: bpy.props.EnumProperty(
        name="Format",
        description="Select the file format to use for syncing with Unreal Engine",
        items=[
            ('FBX', "FBX (.fbx)", "Standard FBX format"),
            ('GLTF', "glTF (.glb)", "Fast, modern PBR format (Binary glTF)"),
            ('USDZ', "USDZ (.usdc)", "Universal Scene Description"),
        ],
        default='FBX'
    )
    enable_mcp: bpy.props.BoolProperty(
        name="Enable AI MCP",
        description="Enable metadata and integration hooks for AI workflows.",
        default=True
    )
    ai_provider: bpy.props.StringProperty(
        name="AI Provider",
        description="Optional AI provider name for MCP/AISync workflows.",
        default="LocalAI"
    )
    livelink_active: bpy.props.BoolProperty(
        name="Live Link Active",
        description="Is Live Link currently sending UDP packets?",
        default=False
    )
    auto_sync_gdrive: bpy.props.BoolProperty(
        name="Auto-Sync Google Drive",
        description="Automatically trigger Google Drive save after exporting",
        default=False
    )


# ---------------------------------------------------------------------------
# Google Drive Entry – one slot in the collection (up to 10)
# ---------------------------------------------------------------------------
class UBSyncGoogleDriveEntry(bpy.types.PropertyGroup):
    label: bpy.props.StringProperty(
        name="Label",
        description="Friendly name for this Google Drive (e.g. 'Work Drive', 'Personal')",
        default="My Drive",
    )
    path: bpy.props.StringProperty(
        name="Folder Path",
        description="Local sync folder for this Google Drive (e.g. G:\\My Drive)",
        subtype='DIR_PATH',
        default="",
    )


# ---------------------------------------------------------------------------
# Addon Preferences (Edit → Preferences → Add-ons → Unreal-Blender Sync)
# ---------------------------------------------------------------------------
class UBSyncPreferences(bpy.types.AddonPreferences):
    bl_idname = "blender_addon"

    default_unreal_project_path: bpy.props.StringProperty(
        name="Unreal Project Path",
        subtype='DIR_PATH',
        default=""
    )
    default_export_folder: bpy.props.StringProperty(
        name="Default Export Folder",
        subtype='DIR_PATH',
        default=""
    )
    sync_folder: bpy.props.StringProperty(
        name="Sync Folder",
        description="Folder for Unreal<->Blender JSON communication (e.g., <UnrealProject>/Saved/BlenderSync)",
        subtype='DIR_PATH',
        default=""
    )

    # Dynamic storage configuration fields
    dropbox_path: bpy.props.StringProperty(
        name="Dropbox Path",
        subtype='DIR_PATH',
        default=""
    )
    gdrive_1_meshes: bpy.props.StringProperty(
        name="GDrive Meshes",
        subtype='DIR_PATH',
        default=""
    )
    gdrive_2_skins: bpy.props.StringProperty(
        name="GDrive Skins",
        subtype='DIR_PATH',
        default=""
    )
    gdrive_3_anims: bpy.props.StringProperty(
        name="GDrive Anims",
        subtype='DIR_PATH',
        default=""
    )
    gdrive_4_audio: bpy.props.StringProperty(
        name="GDrive Audio",
        subtype='DIR_PATH',
        default=""
    )
    asset_library_path: bpy.props.StringProperty(
        name="Asset Library Path",
        subtype='DIR_PATH',
        default=""
    )

    # Google Drive slots (up to 10)
    google_drives: bpy.props.CollectionProperty(type=UBSyncGoogleDriveEntry)

    def draw(self, context):
        layout = self.layout

        # ── Unreal Paths ──
        box = layout.box()
        box.label(text="Unreal Engine Paths", icon='GHOST_ENABLED')
        box.prop(self, 'default_unreal_project_path')
        box.prop(self, 'default_export_folder')
        box.prop(self, 'sync_folder')

        # ── AI / MCP ──
        box = layout.box()
        box.label(text="AI / MCP", icon='LIGHT')
        box.prop(context.scene.ubsync_settings, 'enable_mcp')
        box.prop(context.scene.ubsync_settings, 'ai_provider')

        # ── Dynamic Storage Configuration ──
        box = layout.box()
        box.label(text="Dynamic storage configuration", icon='DISK_DRIVE')
        box.prop(self, 'dropbox_path')
        box.prop(self, 'gdrive_1_meshes')
        box.prop(self, 'gdrive_2_skins')
        box.prop(self, 'gdrive_3_anims')
        box.prop(self, 'gdrive_4_audio')
        box.prop(self, 'asset_library_path')

        # ── Google Drive ──
        box = layout.box()
        header = box.row()
        header.label(text="Google Drive Folders", icon='URL')
        count = len(self.google_drives)
        header.label(text=f"{count} / 10")

        for i, entry in enumerate(self.google_drives):
            row = box.row(align=True)

            # Drive number badge
            sub = row.row(align=True)
            sub.scale_x = 0.3
            sub.label(text=f"#{i + 1}")

            # Label + path
            row.prop(entry, "label", text="")
            row.prop(entry, "path", text="")

            # Remove button
            op = row.operator("ubsync.remove_gdrive", text="", icon='X')
            op.index = i

        # Add button (only if < 10)
        if count < 10:
            row = box.row()
            row.operator("ubsync.add_gdrive", text="Add Google Drive", icon='ADD')
        else:
            box.label(text="Maximum 10 drives reached.", icon='INFO')
