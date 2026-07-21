import os
import bpy
import json
import time
from .utils import get_sync_dir
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatProperty,
    EnumProperty,
    IntProperty,
)
from bpy_extras.io_utils import ExportHelper, ImportHelper


def get_addon_prefs(context):
    """Safely get addon preferences."""
    addon = context.preferences.addons.get(__package__)
    if addon:
        return addon.preferences
    return None


def resolve_export_path(context, override_path):
    """Resolve the export file path from override, scene settings, or addon prefs."""
    if override_path and override_path.strip():
        return bpy.path.abspath(override_path)

    settings = context.scene.ubsync_settings
    if settings.export_path and settings.export_path.strip():
        return bpy.path.abspath(settings.export_path)

    addon_prefs = get_addon_prefs(context)
    if addon_prefs and addon_prefs.default_export_folder and addon_prefs.default_export_folder.strip():
        return bpy.path.abspath(os.path.join(addon_prefs.default_export_folder, "unreal_export.fbx"))

    # Fallback: use route_asset for routing to asset library or gdrive
    from .utils import route_asset
    return route_asset("mesh", "unreal_export.fbx", context)


def resolve_import_path(context, override_path):
    """Resolve the import file path from override, scene settings, or addon prefs."""
    if override_path and override_path.strip():
        return bpy.path.abspath(override_path)

    settings = context.scene.ubsync_settings
    if settings.import_path and settings.import_path.strip():
        return bpy.path.abspath(settings.import_path)

    return ""


# ---------------------------------------------------------------------------
# Export Operator  –  Settings popup → File browser → Export
# ---------------------------------------------------------------------------
class UBSyncExportToUnrealOperator(bpy.types.Operator, ExportHelper):
    bl_idname = "ubsync.export_to_unreal"
    bl_label = "Export Selected to Unreal"
    bl_description = "Export selected Blender objects to an Unreal-compatible FBX file"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".fbx"
    filter_glob: StringProperty(default="*.fbx", options={'HIDDEN'})

    # ── Unreal Target Settings ──────────────────────────────────────────────
    unreal_version: EnumProperty(
        name="Unreal Version",
        description="Target Unreal Engine version (adjusts default settings)",
        items=[
            ('UE5', "Unreal Engine 5.x", "Optimised for UE 5.0 – 5.8"),
            ('UE4', "Unreal Engine 4.x", "Legacy UE4 compatible settings"),
        ],
        default='UE5',
    )

    # ── Geometry ────────────────────────────────────────────────────────────
    export_mesh: BoolProperty(
        name="Meshes",
        description="Include mesh objects in the export",
        default=True,
    )
    export_armature: BoolProperty(
        name="Armatures",
        description="Include armatures / skeletons in the export",
        default=True,
    )
    export_material_json: BoolProperty(
        name="Material JSON",
        description="Export material nodes as JSON for Unreal",
        default=True,
    )
    export_retarget_config: BoolProperty(
        name="Retarget Config",
        description="Export Rigify bone mapping JSON",
        default=True,
    )
    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply mesh modifiers before exporting",
        default=True,
    )
    smoothing: EnumProperty(
        name="Smoothing",
        description="How to export smoothing / normals",
        items=[
            ('FACE', "Face", "Write face smoothing"),
            ('EDGE', "Edge", "Write edge smoothing"),
            ('OFF', "None", "Don't write smoothing data"),
        ],
        default='FACE',
    )
    global_scale: FloatProperty(
        name="Scale",
        description="Global scale factor applied on export",
        default=1.0,
        min=0.001,
        max=1000.0,
    )

    # ── Skeleton / Bones ────────────────────────────────────────────────────
    add_leaf_bones: BoolProperty(
        name="Add Leaf Bones",
        description="Add an extra bone at the tip of each chain (usually OFF for Unreal)",
        default=False,
    )
    only_deform_bones: BoolProperty(
        name="Only Deform Bones",
        description="Only export bones marked as Deform",
        default=True,
    )

    # ── Animation ───────────────────────────────────────────────────────────
    include_animation: BoolProperty(
        name="Export Animation",
        description="Bake and include animation data",
        default=True,
    )
    anim_all_bones: BoolProperty(
        name="Key All Bones",
        description="Force a key on every bone each frame",
        default=True,
    )
    anim_nla_strips: BoolProperty(
        name="NLA Strips",
        description="Export each NLA strip as a separate animation take",
        default=False,
    )
    anim_all_actions: BoolProperty(
        name="All Actions",
        description="Export every action as a separate animation take",
        default=False,
    )
    simplify_factor: FloatProperty(
        name="Simplify",
        description="How much to simplify baked animation (0 = disabled)",
        default=0.0,
        min=0.0,
        max=10.0,
    )

    # ── Textures & Materials ────────────────────────────────────────────────
    embed_textures: BoolProperty(
        name="Embed Textures",
        description="Pack textures inside the FBX file",
        default=True,
    )
    path_mode: EnumProperty(
        name="Path Mode",
        description="How to handle file paths for textures",
        items=[
            ('COPY', "Copy", "Copy textures next to the FBX (or embed)"),
            ('RELATIVE', "Relative", "Use relative paths"),
            ('ABSOLUTE', "Absolute", "Use absolute paths"),
            ('AUTO', "Auto", "Let Blender decide"),
        ],
        default='COPY',
    )

    # ── Axis / Transform ───────────────────────────────────────────────────
    forward_axis: EnumProperty(
        name="Forward",
        description="Forward axis for Unreal",
        items=[
            ('-Z', "-Z Forward", ""),
            ('Z', "Z Forward", ""),
            ('-Y', "-Y Forward", ""),
            ('Y', "Y Forward", ""),
            ('-X', "-X Forward", ""),
            ('X', "X Forward", ""),
        ],
        default='-Z',
    )
    up_axis: EnumProperty(
        name="Up",
        description="Up axis for Unreal",
        items=[
            ('Y', "Y Up", ""),
            ('Z', "Z Up", ""),
            ('X', "X Up", ""),
        ],
        default='Y',
    )
    apply_unit_scale: BoolProperty(
        name="Apply Unit Scale",
        description="Apply the current scene unit scale on export",
        default=True,
    )
    bake_space_transform: BoolProperty(
        name="Apply Transform",
        description="Bake object transforms into the mesh",
        default=True,
    )

    # ── Invoke: show the settings popup ─────────────────────────────────────
    def invoke(self, context, event):
        fmt = context.scene.ubsync_settings.sync_format
        if fmt == 'GLTF':
            self.filename_ext = ".glb"
            self.filter_glob = "*.glb;*.gltf"
        elif fmt == 'USDZ':
            self.filename_ext = ".usdc"
            self.filter_glob = "*.usdc;*.usd;*.usdz"
        else:
            self.filename_ext = ".fbx"
            self.filter_glob = "*.fbx"

        # Pre-fill the filepath
        resolved = resolve_export_path(context, "")
        self.filepath = resolved if resolved else f"unreal_export{self.filename_ext}"

        # Open the file browser which also shows our custom draw panel
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    # ── Draw: organised settings panel inside the file browser ──────────────
    def draw(self, context):
        layout = self.layout

        # ── Unreal Target ──
        box = layout.box()
        box.label(text="Unreal Target", icon='GHOST_ENABLED')
        box.prop(self, "unreal_version")

        # ── Include ──
        box = layout.box()
        box.label(text="Include", icon='OUTLINER_OB_MESH')
        row = box.row(align=True)
        row.prop(self, "export_mesh", toggle=True)
        row.prop(self, "export_armature", toggle=True)
        row = box.row(align=True)
        row.prop(self, "export_material_json", toggle=True)
        row.prop(self, "export_retarget_config", toggle=True)

        # ── Geometry ──
        box = layout.box()
        box.label(text="Geometry", icon='MESH_DATA')
        box.prop(self, "apply_modifiers")
        box.prop(self, "smoothing")
        box.prop(self, "global_scale")

        # ── Skeleton ──
        box = layout.box()
        box.label(text="Skeleton / Bones", icon='BONE_DATA')
        box.prop(self, "add_leaf_bones")
        box.prop(self, "only_deform_bones")

        # ── Animation ──
        box = layout.box()
        box.label(text="Animation", icon='ACTION')
        box.prop(self, "include_animation")
        col = box.column()
        col.enabled = self.include_animation
        col.prop(self, "anim_all_bones")
        col.prop(self, "anim_nla_strips")
        col.prop(self, "anim_all_actions")
        col.prop(self, "simplify_factor")

        # ── Textures ──
        box = layout.box()
        box.label(text="Textures & Materials", icon='MATERIAL')
        box.prop(self, "embed_textures")
        box.prop(self, "path_mode")

        # ── Transform ──
        box = layout.box()
        box.label(text="Transform / Axis", icon='ORIENTATION_GLOBAL')
        row = box.row()
        row.prop(self, "forward_axis")
        row.prop(self, "up_axis")
        box.prop(self, "apply_unit_scale")
        box.prop(self, "bake_space_transform")

    # ── Execute: perform the actual export ──────────────────────────────────
    def execute(self, context):
        if not self.filepath or not self.filepath.strip():
            self.report({'ERROR'}, "No export path specified.")
            return {'CANCELLED'}

        filepath = bpy.path.abspath(self.filepath)
        fmt = context.scene.ubsync_settings.sync_format
        
        # Ensure proper extension
        if fmt == 'GLTF' and not (filepath.lower().endswith('.glb') or filepath.lower().endswith('.gltf')):
            filepath += ".glb"
        elif fmt == 'USDZ' and not (filepath.lower().endswith('.usdc') or filepath.lower().endswith('.usd') or filepath.lower().endswith('.usdz')):
            filepath += ".usdc"
        elif fmt == 'FBX' and not filepath.lower().endswith(".fbx"):
            filepath += ".fbx"

        export_dir = os.path.dirname(filepath)
        if export_dir and not os.path.isdir(export_dir):
            try:
                os.makedirs(export_dir, exist_ok=True)
            except OSError as e:
                self.report({'ERROR'}, f"Cannot create export folder: {e}")
                return {'CANCELLED'}

        # Build object_types from toggles
        object_types = set()
        if self.export_mesh:
            object_types.add('MESH')
        if self.export_armature:
            object_types.add('ARMATURE')
        if not object_types:
            self.report({'WARNING'}, "Enable at least Meshes or Armatures to export.")
            return {'CANCELLED'}

        selected = [o for o in context.selected_objects if o.type in object_types]
        if not selected:
            self.report({'WARNING'}, "Select at least one mesh or armature to export.")
            return {'CANCELLED'}

        try:
            if fmt == 'GLTF':
                bpy.ops.export_scene.gltf(
                    filepath=filepath,
                    use_selection=True,
                    export_format='GLB' if filepath.endswith('.glb') else 'GLTF_SEPARATE',
                    export_materials='EXPORT',
                    export_animations=self.include_animation,
                    export_apply=self.apply_modifiers
                )
            elif fmt == 'USDZ':
                bpy.ops.wm.usd_export(
                    filepath=filepath,
                    selected_objects_only=True,
                    export_animation=self.include_animation,
                    export_hair=True
                )
            else:
                bpy.ops.export_scene.fbx(
                    filepath=filepath,
                    use_selection=True,
                    global_scale=self.global_scale,
                    apply_unit_scale=self.apply_unit_scale,
                    bake_space_transform=self.bake_space_transform,
                    object_types=object_types,
                    mesh_smooth_type=self.smoothing,
                    add_leaf_bones=self.add_leaf_bones,
                    path_mode=self.path_mode,
                    embed_textures=self.embed_textures,
                    use_mesh_modifiers=self.apply_modifiers,
                    use_armature_deform_only=self.only_deform_bones,
                    bake_anim=self.include_animation,
                    bake_anim_use_all_bones=self.anim_all_bones,
                    bake_anim_use_nla_strips=self.anim_nla_strips,
                    bake_anim_use_all_actions=self.anim_all_actions,
                    bake_anim_simplify_factor=self.simplify_factor,
                    axis_forward=self.forward_axis,
                    axis_up=self.up_axis,
                )
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}
            
        from .materials import export_materials_to_json
        from .retargeting import export_retarget_config as export_retarget

        if self.export_material_json and 'MESH' in object_types:
            mat_path = filepath.replace(".fbx", "_materials.json").replace(".glb", "_materials.json").replace(".usdc", "_materials.json")
            export_materials_to_json(selected, mat_path)
            
        if self.export_retarget_config and 'ARMATURE' in object_types:
            retarget_path = filepath.replace(".fbx", "_retarget.json").replace(".glb", "_retarget.json").replace(".usdc", "_retarget.json")
            export_retarget(selected, retarget_path)

        context.scene.ubsync_settings.export_path = filepath
        self.report({'INFO'}, f"Exported to: {filepath}")
        
        prefs = get_addon_prefs(context)
        if prefs and prefs.auto_sync_gdrive:
            try:
                bpy.ops.ubsync.save_to_gdrive('EXEC_DEFAULT', drive_index='0')
                self.report({'INFO'}, "Auto-Synced to Google Drive")
            except Exception as e:
                self.report({'WARNING'}, f"Auto-Sync failed: {e}")
                
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Import Operator  –  File browser with settings panel → Import
# ---------------------------------------------------------------------------
class UBSyncImportFromUnrealOperator(bpy.types.Operator, ImportHelper):
    bl_idname = "ubsync.import_from_unreal"
    bl_label = "Import from Unreal"
    bl_description = "Import an FBX file exported from Unreal Engine"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".fbx"
    filter_glob: StringProperty(default="*.fbx", options={'HIDDEN'})

    # ── Geometry ────────────────────────────────────────────────────────────
    import_normals: BoolProperty(
        name="Custom Normals",
        description="Import custom normals from the FBX",
        default=True,
    )
    auto_bone_orient: BoolProperty(
        name="Auto Bone Orientation",
        description="Automatically align imported bones",
        default=True,
    )
    global_scale: FloatProperty(
        name="Scale",
        description="Global scale factor on import",
        default=1.0,
        min=0.001,
        max=1000.0,
    )

    # ── Animation ───────────────────────────────────────────────────────────
    import_animation: BoolProperty(
        name="Import Animation",
        description="Import animation data from the FBX",
        default=True,
    )
    anim_offset: FloatProperty(
        name="Animation Offset",
        description="Offset applied to animation (in frames)",
        default=0.0,
    )
    ignore_leaf_bones: BoolProperty(
        name="Ignore Leaf Bones",
        description="Skip importing extra leaf / end bones",
        default=True,
    )

    # ── Textures ────────────────────────────────────────────────────────────
    image_search: BoolProperty(
        name="Image Search",
        description="Search for missing textures in nearby directories",
        default=True,
    )

    # ── Axis / Transform ───────────────────────────────────────────────────
    forward_axis: EnumProperty(
        name="Forward",
        items=[
            ('-Z', "-Z Forward", ""),
            ('Z', "Z Forward", ""),
            ('-Y', "-Y Forward", ""),
            ('Y', "Y Forward", ""),
            ('-X', "-X Forward", ""),
            ('X', "X Forward", ""),
        ],
        default='-Z',
    )
    up_axis: EnumProperty(
        name="Up",
        items=[
            ('Y', "Y Up", ""),
            ('Z', "Z Up", ""),
            ('X', "X Up", ""),
        ],
        default='Y',
    )
    manual_orient: BoolProperty(
        name="Manual Orientation",
        description="Use the axis settings above instead of the FBX file's own orientation",
        default=False,
    )

    # ── Invoke ──────────────────────────────────────────────────────────────
    def invoke(self, context, event):
        fmt = context.scene.ubsync_settings.sync_format
        if fmt == 'GLTF':
            self.filename_ext = ".glb"
            self.filter_glob = "*.glb;*.gltf;*.uasset"
        elif fmt == 'USDZ':
            self.filename_ext = ".usd"
            self.filter_glob = "*.usd;*.usdc;*.usdz;*.uasset"
        else:
            self.filename_ext = ".fbx"
            self.filter_glob = "*.fbx;*.uasset"

        resolved = resolve_import_path(context, "")
        self.filepath = resolved if resolved else ""
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    # ── Draw: settings panel inside the file browser ────────────────────────
    def draw(self, context):
        layout = self.layout

        # ── Geometry ──
        box = layout.box()
        box.label(text="Geometry", icon='MESH_DATA')
        box.prop(self, "import_normals")
        box.prop(self, "global_scale")

        # ── Skeleton ──
        box = layout.box()
        box.label(text="Skeleton / Bones", icon='BONE_DATA')
        box.prop(self, "auto_bone_orient")
        box.prop(self, "ignore_leaf_bones")

        # ── Animation ──
        box = layout.box()
        box.label(text="Animation", icon='ACTION')
        box.prop(self, "import_animation")
        col = box.column()
        col.enabled = self.import_animation
        col.prop(self, "anim_offset")

        # ── Textures ──
        box = layout.box()
        box.label(text="Textures", icon='IMAGE_DATA')
        box.prop(self, "image_search")

        # ── Transform ──
        box = layout.box()
        box.label(text="Transform / Axis", icon='ORIENTATION_GLOBAL')
        box.prop(self, "manual_orient")
        col = box.column()
        col.enabled = self.manual_orient
        row = col.row()
        row.prop(self, "forward_axis")
        row.prop(self, "up_axis")

    # ── Execute ─────────────────────────────────────────────────────────────
    def execute(self, context):
        if not self.filepath or not self.filepath.strip():
            self.report({'ERROR'}, "No import path specified.")
            return {'CANCELLED'}

        filepath = bpy.path.abspath(self.filepath)

        if not os.path.isfile(filepath):
            self.report({'ERROR'}, f"File not found: {filepath}")
            return {'CANCELLED'}

        _, ext = os.path.splitext(filepath)
        fmt = context.scene.ubsync_settings.sync_format

        if ext.lower() == '.uasset':
            import json
            import time
            
            # Use the default export folder or look up the Unreal Project path
            prefs = context.preferences.addons[__package__].preferences
            unreal_path = prefs.default_unreal_project_path
            
            if not unreal_path or not os.path.isdir(unreal_path):
                # Fallback: if we are selecting a file inside an Unreal project, we can guess the path
                if "Content" in filepath:
                    unreal_path = filepath.split("Content")[0]
                else:
                    self.report({'ERROR'}, "Please set your Unreal Project Path in Add-on Preferences to use direct .uasset import.")
                    return {'CANCELLED'}
                    
            sync_dir = os.path.join(unreal_path, "Saved", "BlenderSync")
            os.makedirs(sync_dir, exist_ok=True)
            
            req_file = os.path.join(sync_dir, "request.json")
            resp_file = os.path.join(sync_dir, "response.json")
            tmp_file = os.path.join(sync_dir, "request.tmp")
            
            if os.path.exists(resp_file):
                try:
                    os.remove(resp_file)
                except OSError:
                    pass
                
            with open(tmp_file, 'w') as f:
                json.dump({
                    "action": "export_uasset",
                    "filepath": filepath,
                    "format": fmt
                }, f)
            
            # Atomic rename so Unreal directory watcher doesn't read an incomplete file
            if os.path.exists(req_file):
                try:
                    os.remove(req_file)
                except OSError:
                    pass
            os.rename(tmp_file, req_file)
                
            # Poll for response (max 10 seconds)
            success = False
            for _ in range(100):
                if os.path.exists(resp_file):
                    try:
                        with open(resp_file, 'r') as f:
                            resp = json.load(f)
                            if resp.get("status") == "success":
                                filepath = resp.get("filepath")
                                _, ext = os.path.splitext(filepath)
                                success = True
                                break
                            else:
                                self.report({'ERROR'}, "Unreal failed to export the uasset.")
                                return {'CANCELLED'}
                    except json.JSONDecodeError:
                        pass # Still writing
                time.sleep(0.1)
                
            if not success:
                self.report({'ERROR'}, f"Timed out! Expected response at: {resp_file}. Ensure Unreal Engine is open and compiled.")
                return {'CANCELLED'}

        try:
            if fmt == 'GLTF' and ext.lower() in ['.glb', '.gltf']:
                bpy.ops.import_scene.gltf(
                    filepath=filepath,
                    import_pack_images=True,
                    bone_heuristic='FORTUNE'
                )
            elif fmt == 'USDZ' and ext.lower() in ['.usd', '.usdc', '.usdz']:
                bpy.ops.wm.usd_import(
                    filepath=filepath,
                    scale=self.global_scale,
                    import_animation=self.import_animation
                )
            elif fmt == 'FBX' and ext.lower() == '.fbx':
                bpy.ops.import_scene.fbx(
                    filepath=filepath,
                    global_scale=self.global_scale,
                    axis_forward=self.forward_axis,
                    axis_up=self.up_axis,
                    automatic_bone_orientation=self.auto_bone_orient,
                    use_custom_normals=self.import_normals,
                    use_image_search=self.image_search,
                    use_anim=self.import_animation,
                    anim_offset=self.anim_offset,
                    ignore_leaf_bones=self.ignore_leaf_bones,
                    use_manual_orientation=self.manual_orient,
                )
            else:
                self.report({'ERROR'}, f"File extension {ext} does not match selected format {fmt}.")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            return {'CANCELLED'}

        context.scene.ubsync_settings.import_path = filepath
        self.report({'INFO'}, f"Imported: {filepath}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Auto Weight Paint Operator
# ---------------------------------------------------------------------------
class UBSyncAutoWeightOperator(bpy.types.Operator):
    bl_idname = "ubsync.auto_weight"
    bl_label = "Auto Weight Paint"
    bl_description = "Automatically weight-paint the selected mesh to its armature"

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh object first.")
            return {'CANCELLED'}

        # Find the armature — modifiers → parent → selection
        armature = None
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                armature = mod.object
                break

        if armature is None and obj.parent and obj.parent.type == 'ARMATURE':
            armature = obj.parent

        if armature is None:
            for sel in context.selected_objects:
                if sel.type == 'ARMATURE':
                    armature = sel
                    break

        if armature is None:
            self.report({'WARNING'},
                        "No armature found. Add an Armature modifier, parent to an armature, "
                        "or select an armature together with the mesh.")
            return {'CANCELLED'}

        try:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            armature.select_set(True)
            context.view_layer.objects.active = armature

            bpy.ops.object.parent_set(type='ARMATURE_AUTO')

            context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

            self.report({'INFO'}, "Auto weight painting complete.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Auto weight painting failed: {e}")
            return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Retarget Setup Operator
# ---------------------------------------------------------------------------
class UBSyncRetargetOperator(bpy.types.Operator):
    bl_idname = "ubsync.retarget"
    bl_label = "Easy Retarget Setup"
    bl_description = "Create a retarget helper bone on the selected armature"

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'WARNING'}, "Select an armature first.")
            return {'CANCELLED'}

        try:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.select_all(action='DESELECT')
            armature.select_set(True)
            context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='EDIT')

            if 'UBSync_RetargetRoot' not in armature.data.edit_bones:
                bone = armature.data.edit_bones.new('UBSync_RetargetRoot')
                bone.head = (0.0, 0.0, 0.0)
                bone.tail = (0.0, 0.0, 10.0)
                self.report({'INFO'}, "Retarget helper bone created.")
            else:
                self.report({'INFO'}, "Retarget helper bone already exists.")

            bpy.ops.object.mode_set(mode='OBJECT')
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Retarget setup failed: {e}")
            return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Quick Export: Mesh Only
# ---------------------------------------------------------------------------
class UBSyncExportMeshOnlyOperator(bpy.types.Operator):
    bl_idname = "ubsync.export_mesh_only"
    bl_label = "Export Mesh Only"
    bl_description = "Quickly export only the selected mesh (no rig, no animation)"

    def execute(self, context):
        filepath = resolve_export_path(context, "")
        if not filepath:
            self.report({'ERROR'}, "Please use the main 'Export Selected to Unreal' button first to set a path.")
            return {'CANCELLED'}

        if not filepath.lower().endswith(".fbx"):
            filepath += ".fbx"

        # Modify filename slightly to avoid overwriting the main export if desired,
        # or just overwrite it. We'll overwrite the main one for simplicity.
        export_dir = os.path.dirname(filepath)
        os.makedirs(export_dir, exist_ok=True)

        selected = [o for o in context.selected_objects if o.type == 'MESH']
        if not selected:
            self.report({'WARNING'}, "Select at least one MESH object.")
            return {'CANCELLED'}

        try:
            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=True,
                apply_unit_scale=True,
                bake_space_transform=True,
                object_types={'MESH'},
                mesh_smooth_type='FACE',
                path_mode='COPY',
                embed_textures=True,
                use_mesh_modifiers=True,
                bake_anim=False,
                axis_forward='-Z',
                axis_up='Y',
            )
        except Exception as e:
            self.report({'ERROR'}, f"Mesh-only export failed: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported MESH ONLY to: {filepath}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Quick Export: Animation Only
# ---------------------------------------------------------------------------
class UBSyncExportAnimOnlyOperator(bpy.types.Operator):
    bl_idname = "ubsync.export_anim_only"
    bl_label = "Export Animation Only"
    bl_description = "Quickly export only the skeletal animation (no meshes)"

    def execute(self, context):
        filepath = resolve_export_path(context, "")
        if not filepath:
            self.report({'ERROR'}, "Please use the main 'Export Selected to Unreal' button first to set a path.")
            return {'CANCELLED'}

        # Suffix the file with _Anim so we don't overwrite the main mesh file
        base, ext = os.path.splitext(filepath)
        filepath = f"{base}_Anim{ext if ext else '.fbx'}"

        export_dir = os.path.dirname(filepath)
        os.makedirs(export_dir, exist_ok=True)

        selected = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if not selected:
            self.report({'WARNING'}, "Select at least one ARMATURE object.")
            return {'CANCELLED'}

        try:
            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=True,
                apply_unit_scale=True,
                bake_space_transform=True,
                object_types={'ARMATURE'},
                add_leaf_bones=False,
                use_armature_deform_only=True,
                bake_anim=True,
                bake_anim_use_all_bones=True,
                axis_forward='-Z',
                axis_up='Y',
            )
        except Exception as e:
            self.report({'ERROR'}, f"Animation-only export failed: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported ANIMATION ONLY to: {filepath}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Disable / Remove Add-on Operator
# ---------------------------------------------------------------------------
class UBSyncUninstallOperator(bpy.types.Operator):
    bl_idname = "ubsync.uninstall_addon"
    bl_label = "Disable / Remove Add-on"
    bl_description = "Disable this add-on and optionally delete its files from the Blender add-ons folder"

    delete_files: bpy.props.BoolProperty(
        name="Delete Files",
        description="Delete the add-on files after disabling it",
        default=False,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        addon_path = os.path.dirname(__file__)
        layout.label(text=f"Addon path: {addon_path}")
        layout.prop(self, "delete_files")
        layout.label(text="Disabling is safe; deleting files removes them from disk.")

    def execute(self, context):
        mod_name = __package__
        try:
            bpy.ops.preferences.addon_disable(module=mod_name)
        except Exception as e:
            self.report({'WARNING'}, f"Could not disable add-on: {e}")

        if self.delete_files:
            try:
                import shutil
                addon_dir = os.path.dirname(__file__)
                shutil.rmtree(addon_dir)
                self.report({'INFO'}, "Add-on disabled and files removed. Restart Blender.")
            except Exception as e:
                self.report({'ERROR'}, f"Could not delete add-on files: {e}")
                return {'CANCELLED'}
        else:
            self.report({'INFO'}, "Add-on disabled. Restart Blender to complete removal.")

        return {'FINISHED'}

