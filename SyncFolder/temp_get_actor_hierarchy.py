import unreal, json
actors = unreal.EditorLevelLibrary.get_all_level_actors()
out = []
for a in actors:
    if a:
        loc = a.get_actor_location()
        out.append({
            "name": a.get_actor_label(),
            "path": a.get_path_name(),
            "class": a.get_class().get_name(),
            "location": {"x": loc.x, "y": loc.y, "z": loc.z}
        })
out_path = f"C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder/actor_hierarchy.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f)
