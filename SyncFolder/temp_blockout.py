import unreal
astatic = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cylinder.Cylinder")
if astatic:
    actor = unreal.EditorLevelLibrary.spawn_actor_from_object(astatic, unreal.Vector(350, 4420, 40))
    if actor:
        actor.set_actor_label("Tavern_Barrel_2")
        actor.set_actor_scale3d(unreal.Vector(0.6, 0.6, 0.8))
        unreal.log("Spawned blockout: Tavern_Barrel_2")
else:
    unreal.log_warning("Could not load mesh: /Engine/BasicShapes/Cylinder.Cylinder")
