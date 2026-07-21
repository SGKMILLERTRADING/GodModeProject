import unreal, os

log_path = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder/ue_debug.log"
def log(msg):
    with open(log_path, "a") as f:
        f.write(str(msg) + "\n")

if os.path.exists(log_path):
    os.remove(log_path)

log("Starting export_texture2d test")
try:
    rt = unreal.RenderingLibrary.create_render_target2d(None, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    log("Created RT")
    
    cam_loc, cam_rot = unreal.Vector(0, 0, 100), unreal.Rotator(0, 0, 0)
    capture_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, cam_loc)
    log(f"Spawned capture actor: {capture_actor}")
    
    if capture_actor:
        comp = capture_actor.get_component_by_class(unreal.SceneCaptureComponent2D)
        log(f"Component: {comp}")
        if comp:
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
            comp.capture_scene()
            log("Captured scene")

        tex = unreal.RenderingLibrary.render_target_create_static_texture2d_editor_only(rt, "TempShotTex")
        log(f"Created static tex: {tex}")
        
        if tex:
            target_dir = "C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder"
            log("Calling export_texture2d")
            unreal.RenderingLibrary.export_texture2d(None, tex, target_dir, "ue_screenshot.png")
            log("Export call done")
            
        unreal.EditorLevelLibrary.destroy_actor(capture_actor)
except Exception as ex:
    log(f"Error: {ex}")
