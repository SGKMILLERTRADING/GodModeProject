import os
import shutil
import bpy
from bpy.props import StringProperty, EnumProperty, BoolProperty


def get_addon_prefs(context):
    """Safely get addon preferences."""
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def get_drive_items(self, context):
    """Build the EnumProperty items list from configured Google Drives."""
    prefs = get_addon_prefs(context)
    if not prefs:
        return [('NONE', "No drives configured", "")]

    items = []
    for i, entry in enumerate(prefs.google_drives):
        if entry.path and entry.path.strip():
            label = entry.label if entry.label.strip() else f"Drive {i + 1}"
            items.append((str(i), label, entry.path))

    if not items:
        return [('NONE', "No drives configured", "")]

    return items


# ---------------------------------------------------------------------------
# Save current .blend + FBX exports TO a Google Drive
# ---------------------------------------------------------------------------
class UBSyncSaveToGoogleDriveOperator(bpy.types.Operator):
    bl_idname = "ubsync.save_to_gdrive"
    bl_label = "Save to Google Drive"
    bl_description = "Copy the current .blend file and any recent FBX exports to a Google Drive folder"
    bl_options = {'REGISTER'}

    drive_index: EnumProperty(
        name="Google Drive",
        description="Which Google Drive to save to",
        items=get_drive_items,
    )
    save_blend: BoolProperty(
        name="Save .blend File",
        description="Copy the current .blend file to the drive",
        default=True,
    )
    save_fbx: BoolProperty(
        name="Save Last FBX Export",
        description="Copy the last FBX export to the drive",
        default=True,
    )
    subfolder: StringProperty(
        name="Subfolder",
        description="Optional subfolder inside the drive (e.g. 'MyProject/Characters')",
        default="UBSync",
    )

    def invoke(self, context, event):
        prefs = get_addon_prefs(context)
        if not prefs or len(prefs.google_drives) == 0:
            self.report({'ERROR'}, "No Google Drive paths configured. Set them up in addon preferences.")
            return {'CANCELLED'}

        has_valid = any(e.path.strip() for e in prefs.google_drives)
        if not has_valid:
            self.report({'ERROR'}, "No Google Drive paths configured. Set them up in addon preferences.")
            return {'CANCELLED'}

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Destination", icon='FILE_FOLDER')
        box.prop(self, "drive_index")
        box.prop(self, "subfolder")

        box = layout.box()
        box.label(text="What to Save", icon='FILE_TICK')
        box.prop(self, "save_blend")
        box.prop(self, "save_fbx")

    def execute(self, context):
        if self.drive_index == 'NONE':
            self.report({'ERROR'}, "No Google Drive configured.")
            return {'CANCELLED'}

        prefs = get_addon_prefs(context)
        idx = int(self.drive_index)
        if idx >= len(prefs.google_drives):
            self.report({'ERROR'}, "Invalid drive selection.")
            return {'CANCELLED'}

        drive_entry = prefs.google_drives[idx]
        drive_path = bpy.path.abspath(drive_entry.path)

        if not os.path.isdir(drive_path):
            self.report({'ERROR'}, f"Drive folder not found: {drive_path}")
            return {'CANCELLED'}

        # Build the target directory
        target_dir = os.path.join(drive_path, self.subfolder) if self.subfolder.strip() else drive_path
        os.makedirs(target_dir, exist_ok=True)

        copied = []

        # Save .blend
        if self.save_blend:
            blend_path = bpy.data.filepath
            if blend_path:
                filename = os.path.basename(blend_path)
                dest = os.path.join(target_dir, filename)
                try:
                    shutil.copy2(blend_path, dest)
                    copied.append(filename)
                except Exception as e:
                    self.report({'WARNING'}, f"Could not copy .blend: {e}")
            else:
                # File has never been saved — save a temp copy
                temp_name = "untitled.blend"
                dest = os.path.join(target_dir, temp_name)
                try:
                    bpy.ops.wm.save_as_mainfile(filepath=dest, copy=True)
                    copied.append(temp_name)
                except Exception as e:
                    self.report({'WARNING'}, f"Could not save .blend copy: {e}")

        # Save last FBX export
        if self.save_fbx:
            settings = context.scene.ubsync_settings
            fbx_path = bpy.path.abspath(settings.export_path) if settings.export_path else ""
            if fbx_path and os.path.isfile(fbx_path):
                filename = os.path.basename(fbx_path)
                dest = os.path.join(target_dir, filename)
                try:
                    shutil.copy2(fbx_path, dest)
                    copied.append(filename)
                except Exception as e:
                    self.report({'WARNING'}, f"Could not copy FBX: {e}")
            else:
                self.report({'WARNING'}, "No FBX export found. Export first, then save to Drive.")

        if copied:
            drive_label = drive_entry.label or f"Drive {idx + 1}"
            self.report({'INFO'}, f"Saved to {drive_label}: {', '.join(copied)}")
        else:
            self.report({'WARNING'}, "Nothing was saved.")

        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Load a .blend or FBX FROM a Google Drive
# ---------------------------------------------------------------------------
class UBSyncLoadFromGoogleDriveOperator(bpy.types.Operator):
    bl_idname = "ubsync.load_from_gdrive"
    bl_label = "Load from Google Drive"
    bl_description = "Browse a Google Drive folder to open a .blend or import an FBX"
    bl_options = {'REGISTER'}

    drive_index: EnumProperty(
        name="Google Drive",
        description="Which Google Drive to load from",
        items=get_drive_items,
    )
    subfolder: StringProperty(
        name="Subfolder",
        description="Subfolder to look in (e.g. 'UBSync')",
        default="UBSync",
    )
    file_type: EnumProperty(
        name="File Type",
        description="What kind of file to look for",
        items=[
            ('BLEND', ".blend File", "Open a Blender project file"),
            ('FBX', ".fbx File", "Import an FBX file"),
            ('BROWSE', "Browse Folder", "Open the drive folder in your file explorer"),
        ],
        default='FBX',
    )

    def invoke(self, context, event):
        prefs = get_addon_prefs(context)
        if not prefs or len(prefs.google_drives) == 0:
            self.report({'ERROR'}, "No Google Drive paths configured. Set them up in addon preferences.")
            return {'CANCELLED'}

        has_valid = any(e.path.strip() for e in prefs.google_drives)
        if not has_valid:
            self.report({'ERROR'}, "No Google Drive paths configured. Set them up in addon preferences.")
            return {'CANCELLED'}

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Source", icon='FILE_FOLDER')
        box.prop(self, "drive_index")
        box.prop(self, "subfolder")

        box = layout.box()
        box.label(text="Action", icon='IMPORT')
        box.prop(self, "file_type")

    def execute(self, context):
        if self.drive_index == 'NONE':
            self.report({'ERROR'}, "No Google Drive configured.")
            return {'CANCELLED'}

        prefs = get_addon_prefs(context)
        idx = int(self.drive_index)
        if idx >= len(prefs.google_drives):
            self.report({'ERROR'}, "Invalid drive selection.")
            return {'CANCELLED'}

        drive_entry = prefs.google_drives[idx]
        drive_path = bpy.path.abspath(drive_entry.path)
        target_dir = os.path.join(drive_path, self.subfolder) if self.subfolder.strip() else drive_path

        if not os.path.isdir(target_dir):
            self.report({'ERROR'}, f"Folder not found: {target_dir}")
            return {'CANCELLED'}

        if self.file_type == 'BROWSE':
            # Open the folder in the OS file explorer
            import subprocess
            import sys
            if sys.platform == 'win32':
                os.startfile(target_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', target_dir])
            else:
                subprocess.Popen(['xdg-open', target_dir])
            self.report({'INFO'}, f"Opened folder: {target_dir}")
            return {'FINISHED'}

        # Find the most recent matching file
        ext = ".blend" if self.file_type == 'BLEND' else ".fbx"
        files = []
        for f in os.listdir(target_dir):
            if f.lower().endswith(ext):
                full = os.path.join(target_dir, f)
                files.append((full, os.path.getmtime(full)))

        if not files:
            self.report({'WARNING'}, f"No {ext} files found in: {target_dir}")
            return {'CANCELLED'}

        # Sort by newest first
        files.sort(key=lambda x: x[1], reverse=True)
        chosen = files[0][0]

        if self.file_type == 'BLEND':
            try:
                bpy.ops.wm.open_mainfile(filepath=chosen)
                self.report({'INFO'}, f"Opened: {os.path.basename(chosen)}")
            except Exception as e:
                self.report({'ERROR'}, f"Failed to open .blend: {e}")
                return {'CANCELLED'}
        else:
            try:
                bpy.ops.import_scene.fbx(
                    filepath=chosen,
                    axis_forward='-Z',
                    axis_up='Y',
                    automatic_bone_orientation=True,
                    use_custom_normals=True,
                    use_image_search=True,
                    use_anim=True,
                )
                context.scene.ubsync_settings.import_path = chosen
                self.report({'INFO'}, f"Imported: {os.path.basename(chosen)}")
            except Exception as e:
                self.report({'ERROR'}, f"FBX import failed: {e}")
                return {'CANCELLED'}

        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Preferences UI: Add / Remove drive entries
# ---------------------------------------------------------------------------
class UBSyncAddGoogleDriveOperator(bpy.types.Operator):
    bl_idname = "ubsync.add_gdrive"
    bl_label = "Add Google Drive"
    bl_description = "Add a new Google Drive folder slot"

    def execute(self, context):
        prefs = get_addon_prefs(context)
        if not prefs:
            return {'CANCELLED'}

        if len(prefs.google_drives) >= 10:
            self.report({'WARNING'}, "Maximum of 10 Google Drive slots reached.")
            return {'CANCELLED'}

        entry = prefs.google_drives.add()
        entry.label = f"Drive {len(prefs.google_drives)}"
        return {'FINISHED'}


class UBSyncRemoveGoogleDriveOperator(bpy.types.Operator):
    bl_idname = "ubsync.remove_gdrive"
    bl_label = "Remove Google Drive"
    bl_description = "Remove a Google Drive folder slot"

    index: bpy.props.IntProperty()

    def execute(self, context):
        prefs = get_addon_prefs(context)
        if not prefs:
            return {'CANCELLED'}

        if 0 <= self.index < len(prefs.google_drives):
            prefs.google_drives.remove(self.index)
        return {'FINISHED'}
