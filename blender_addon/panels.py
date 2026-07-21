import bpy


class UBSyncPanel(bpy.types.Panel):
    bl_label = "Unreal-Blender Sync"
    bl_idname = "VIEW3D_PT_ubsync"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Unreal-Blender'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        addon = context.preferences.addons.get(__package__)
        prefs = addon.preferences if addon else None

        # ── Export / Import ──
        layout.label(text="Blender <-> Unreal Workflow")
        layout.prop(scene.ubsync_settings, 'sync_format')
        layout.prop(scene.ubsync_settings, 'export_path')
        layout.operator('ubsync.export_to_unreal', text='Export Selected to Unreal', icon='EXPORT')
        
        row = layout.row(align=True)
        row.operator('ubsync.export_mesh_only', text='Mesh Only', icon='MESH_DATA')
        row.operator('ubsync.export_anim_only', text='Anim Only', icon='ACTION')
        row.operator('ubsync.export_hair', text='Hair (ABC)', icon='STRANDS')
        
        if prefs:
            layout.prop(prefs, 'auto_sync_gdrive')
            
        layout.separator()
        layout.prop(scene.ubsync_settings, 'import_path')
        layout.operator('ubsync.import_from_unreal', text='Import from Unreal', icon='IMPORT')

        layout.separator()

        # ── Tools ──
        layout.label(text="Tools", icon='TOOL_SETTINGS')
        layout.operator('ubsync.auto_weight', text='Auto Weight Paint', icon='MOD_VERTEX_WEIGHT')
        layout.operator('ubsync.retarget', text='Easy Retarget Setup', icon='BONE_DATA')
        layout.operator('ubsync.uninstall_addon', text='Disable / Remove Add-on', icon='TRASH')

        layout.separator()

        # ── Live Link ──
        layout.label(text="Live Link", icon='RECOVER_LAST')
        if prefs:
            icon = 'PAUSE' if prefs.livelink_active else 'PLAY'
            text = "Stop Live Link" if prefs.livelink_active else "Start Live Link"
            layout.operator('ubsync.toggle_livelink', text=text, icon=icon)
            
        layout.separator()

        # ── Google Drive ──
        layout.label(text="Google Drive Operations", icon='URL')
        row = layout.row(align=True)
        row.operator('ubsync.save_to_gdrive', text='Save to Drive', icon='EXPORT')
        row.operator('ubsync.load_from_gdrive', text='Load from Drive', icon='IMPORT')

        if prefs:
            box = layout.box()
            count = len(prefs.google_drives)
            box.label(text=f"Configured Drives ({count}/10)", icon='FILE_FOLDER')

            for i, entry in enumerate(prefs.google_drives):
                row = box.row(align=True)
                # Label
                row.prop(entry, "label", text="")
                # Path
                row.prop(entry, "path", text="")
                # Remove button
                op = row.operator("ubsync.remove_gdrive", text="", icon='X')
                op.index = i

            if count < 10:
                box.operator("ubsync.add_gdrive", text="Add New Drive", icon='ADD')
            else:
                box.label(text="Maximum 10 drives reached.", icon='INFO')
        else:
            layout.label(text="Addon preferences not found", icon='ERROR')

        layout.separator()

        # ── AI / MCP ──
        layout.label(text='AI / MCP Support')
        layout.prop(scene.ubsync_settings, 'enable_mcp')
        layout.prop(scene.ubsync_settings, 'ai_provider')
        
        from .ai_bridge import is_running
        if is_running:
            layout.operator('ubsync.ai_bridge', text='Stop AI Bridge (Running)', icon='LIGHT')
            layout.label(text="Server active on port 12345", icon='CHECKMARK')
        else:
            layout.operator('ubsync.ai_bridge', text='Start AI Bridge (Stopped)', icon='OUTLINED_LIGHT')
            layout.label(text="Server offline", icon='ERROR')
            
        if scene.ubsync_settings.enable_mcp:
            layout.label(text=f"Provider: {scene.ubsync_settings.ai_provider}")
        else:
            layout.label(text="MCP disabled. Enable to use AI hooks.")

