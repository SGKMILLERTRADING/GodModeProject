import unreal
target_name = "Darric_Shadow_Rim"
actors = unreal.EditorLevelLibrary.get_all_level_actors()
found = False
for a in actors:
    if a and (a.get_actor_label() == target_name or a.get_path_name() == target_name or a.get_name() == target_name or target_name in a.get_name()):
        a.set_actor_location(unreal.Vector(0, 0, 0), False, True)
        if 0 != 0 or 0 != 0 or 0 != 0:
            a.set_actor_rotation(unreal.Rotator(0, 0, 0), False)
        if 1 != 1 or 1 != 1 or 1 != 1:
            a.set_actor_scale3d(unreal.Vector(1, 1, 1))
        unreal.log(f"set_transform: Updated {target_name} transform")
        found = True
        break
if not found:
    unreal.log_warning(f"set_transform: Could not find actor matching {target_name}")
