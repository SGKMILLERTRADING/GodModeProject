# Unreal-Blender Sync Plugin (UE5.8)

This folder contains a starter Unreal Engine 5.8 plugin skeleton for exporting selected assets to Blender.

## What it includes

- `UnrealBlenderSync.uplugin` plugin descriptor
- `Source/UnrealBlenderSync/UnrealBlenderSync.Build.cs` build module
- `Source/UnrealBlenderSync/Public/UnrealBlenderSync.h` module interface
- `Source/UnrealBlenderSync/Private/UnrealBlenderSyncModule.cpp` editor menu hook and export action

## Features

- Adds a `Tools > Export Selected to Blender` menu item in the Level Editor
- Exports mesh, skin weights, hair, and animation via FBX to a project `Saved/BlenderSync/export.fbx`
- Designed as a foundation for future enhancements: material mapping, hair grooms, texture packing, and direct Unreal/Blender pipe

## Notes

This is scaffolding code and needs Unreal Engine 5.8 environment setup to compile. Extend the export path, add metadata export, and integrate with Blender import conventions for full seamless workflow.
