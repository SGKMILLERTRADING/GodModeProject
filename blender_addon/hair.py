import bpy
import os

class UBSyncExportHairOperator(bpy.types.Operator):
    bl_idname = "ubsync.export_hair"
    bl_label = "Export Hair (Alembic)"
    bl_description = "Export selected hair/curves to Alembic (.abc) for Unreal Groom"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        # We assume the main FBX path is stored in scene settings
        settings = context.scene.ubsync_settings
        if not settings.export_path:
            self.report({'ERROR'}, "Set a main export path via 'Export Selected to Unreal' first.")
            return {'CANCELLED'}

        base_path, _ = os.path.splitext(settings.export_path)
        abc_path = f"{base_path}_Groom.abc"

        # Check if we have curves or meshes with particle hair selected
        valid_objs = []
        for obj in context.selected_objects:
            if obj.type == 'CURVES':
                valid_objs.append(obj)
            elif obj.type == 'MESH':
                # Check for particle systems
                if obj.particle_systems:
                    valid_objs.append(obj)

        if not valid_objs:
            self.report({'WARNING'}, "Select a CURVES object or a MESH with a particle system.")
            return {'CANCELLED'}

        try:
            # Export to Alembic
            bpy.ops.wm.alembic_export(
                filepath=abc_path,
                selected=True,
                visible_objects_only=False,
                flatten=False,
                uvs=True,
                packuv=True,
                normals=True,
                vcolors=True,
                face_sets=False,
                subdiv_schema=False,
                apply_subdiv=False,
                curves_as_mesh=False,
                use_instancing=True,
                global_scale=1.0,
                triangulate=False,
                quad_method='BEAUTY',
                ngon_method='BEAUTY',
                export_hair=True,
                export_particles=False,
                export_custom_properties=False,
                as_background_job=False
            )
            self.report({'INFO'}, f"Exported Groom to {abc_path}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export hair: {e}")
            return {'CANCELLED'}
