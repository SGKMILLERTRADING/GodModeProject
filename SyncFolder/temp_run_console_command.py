import unreal
world = unreal.EditorLevelLibrary.get_editor_world()
unreal.SystemLibrary.execute_console_command(world, 'stat fps')
unreal.log(f'Console: stat fps')
