"""
Unreal MCP Bridge
-----------------
This script is a proper MCP server (stdio transport) that LM Studio, Claude Desktop,
Ollama and any MCP-compatible AI client can launch directly.

It translates MCP tool calls -> TCP socket requests -> Unreal Engine MCP server (port 8000).

HOW IT WORKS:
  AI client (LM Studio / Claude Desktop) launches this script via stdio.
  This script listens for JSON-RPC messages on stdin, forwards them to
  the Unreal socket server on 127.0.0.1:8000, and writes the response to stdout.

DO NOT EDIT anything below the ===EDIT ABOVE=== line unless you know what you are doing.
"""

# ===========================  EDIT ONLY THESE TWO LINES  ===========================
UNREAL_HOST = "127.0.0.1"
UNREAL_PORT = 8001
AUTH_TOKEN  = "d9a7f3e8b6c04a92a5f2e1c4b9d7e3a1"   # must match UnrealMCPConfig.ini
# ===================================================================================

import sys, json, socket, traceback

# --------------------------------------------------------------------------
# MCP tool definitions – what the AI sees as available "tools"
# --------------------------------------------------------------------------
TOOLS = [
    {
        "name": "get_actor_hierarchy",
        "description": "List every actor in the current Unreal level with its name and location.",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "create_actor",
        "description": "Spawn a new actor in the Unreal level.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "class": {"type": "string", "description": "Unreal class name, e.g. StaticMeshActor"},
                "name":  {"type": "string", "description": "Display name for the new actor"}
            },
            "required": ["class", "name"]
        }
    },
    {
        "name": "delete_actor",
        "description": "Delete an actor from the current Unreal level by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Exact name of the actor to delete"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "set_transform",
        "description": "Move an actor to a new location in the Unreal level.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name":      {"type": "string",  "description": "Actor name"},
                "transform": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "z": {"type": "number"}
                    },
                    "required": ["x","y","z"]
                }
            },
            "required": ["name","transform"]
        }
    },
    {
        "name": "trigger_sync",
        "description": "Trigger a Blender→Unreal or Unreal→Blender asset sync.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Export type: ALL, MESH, MATERIAL, etc.", "default": "ALL"}
            },
            "required": []
        }
    },
    {
        "name": "get_metadata",
        "description": "Read the Unreal asset metadata JSON from the sync folder.",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "set_metadata",
        "description": "Write/update the Unreal asset metadata JSON in the sync folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "metadata": {"type": "object", "description": "Key-value pairs to store as metadata"}
            },
            "required": ["metadata"]
        }
    },
    {
        "name": "get_asset_hierarchy",
        "description": "List all content-browser assets in the Unreal project.",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "run_editor_command",
        "description": "Execute an arbitrary Unreal Engine console command.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Console command string, e.g. 'stat fps'"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "get_actor_property",
        "description": "Read a property/variable from an actor in the level.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "objectPath": {"type": "string", "description": "The exact object path of the actor (e.g. from get_actor_hierarchy)"},
                "propertyName": {"type": "string", "description": "The name of the property to read"}
            },
            "required": ["objectPath", "propertyName"]
        }
    },
    {
        "name": "set_actor_property",
        "description": "Write/change a property/variable on an actor in the level.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "objectPath": {"type": "string", "description": "The exact object path of the actor"},
                "propertyName": {"type": "string", "description": "The name of the property to set"},
                "propertyValue": {"description": "The new value for the property (can be number, string, object, bool)"}
            },
            "required": ["objectPath", "propertyName", "propertyValue"]
        }
    },
    {
        "name": "call_blueprint_function",
        "description": "Call a custom function or event on a Blueprint actor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "objectPath": {"type": "string", "description": "The exact object path of the Blueprint actor"},
                "functionName": {"type": "string", "description": "The name of the function or event to call"},
                "parameters": {"type": "object", "description": "Key-value pairs of parameters to pass to the function", "default": {}}
            },
            "required": ["objectPath", "functionName"]
        }
    },
    {
        "name": "execute_unreal_python",
        "description": "God Mode: Execute an arbitrary Python script directly inside Unreal Engine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "The full Python code to execute in Unreal Engine."}
            },
            "required": ["script"]
        }
    },
    {
        "name": "take_screenshot",
        "description": "Take a screenshot of the Unreal Engine active viewport/editor window and return it as an image.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "spawn_blockout_primitive",
        "description": "Spawn a blockout primitive (cube, sphere, cylinder, cone, plane) in the Unreal level with an optional material color. Great for AI-driven level layout.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "shape": {"type": "string", "description": "Primitive shape: Cube, Sphere, Cylinder, Cone, or Plane", "default": "Cube"},
                "name":  {"type": "string", "description": "Display name for the actor"},
                "location": {
                    "type": "object",
                    "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}},
                    "default": {"x": 0, "y": 0, "z": 0}
                },
                "scale": {
                    "type": "object",
                    "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}},
                    "default": {"x": 1, "y": 1, "z": 1}
                }
            },
            "required": ["shape", "name"]
        }
    },
    {
        "name": "batch_create_actors",
        "description": "Create multiple actors at once. Pass an array of actor definitions. Each definition should have: shape, name, location (x,y,z), and scale (x,y,z).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "shape": {"type": "string"},
                            "name": {"type": "string"},
                            "location": {"type": "object"},
                            "scale": {"type": "object"}
                        }
                    }
                }
            },
            "required": ["actors"]
        }
    },
    {
        "name": "import_fbx",
        "description": "Import an FBX file from the sync folder into the Unreal project. Optionally run the material processor afterwards.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "FBX filename inside the sync folder (e.g., 'MyMesh.fbx')"},
                "destination": {"type": "string", "description": "Unreal content path to import into (e.g., '/Game/BlenderSync/')", "default": "/Game/BlenderSync/"}
            },
            "required": ["filename"]
        }
    },
    {
        "name": "import_animation_to_unreal",
        "description": "Import an FBX animation to Unreal and target to a skeleton.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "destination_path": {"type": "string", "default": "/Game/Animations"},
                "skeleton_path": {"type": "string"}
            },
            "required": ["filepath", "skeleton_path"]
        }
    },
    {
        "name": "initialize_project_brain",
        "description": "Lead AI initializes the folder structure and generates a Universal Prompt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "dropbox_path": {"type": "string"}
            },
            "required": ["project_name", "dropbox_path"]
        }
    },
    {
        "name": "add_research_note",
        "description": "Creates or overwrites a Markdown research note.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "dropbox_path": {"type": "string"},
                "topic": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["project_name", "dropbox_path", "topic", "content"]
        }
    },
    {
        "name": "read_research_notes",
        "description": "Lists all research notes and returns their content and validation status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "dropbox_path": {"type": "string"}
            },
            "required": ["project_name", "dropbox_path"]
        }
    },
    {
        "name": "validate_code_snippet",
        "description": "Appends a validation header to an existing research note.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "dropbox_path": {"type": "string"},
                "topic": {"type": "string"},
                "is_good": {"type": "boolean"},
                "notes": {"type": "string"}
            },
            "required": ["project_name", "dropbox_path", "topic", "is_good", "notes"]
        }
    },
    # ── Landscape & Terrain Tools ─────────────────────────────────────────────
    {
        "name": "create_landscape",
        "description": "Create a new Landscape actor in the level. Configurable size, sections, and component count.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}, "default": {"x": 0, "y": 0, "z": 0}},
                "scale": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}, "default": {"x": 100, "y": 100, "z": 100}},
                "section_size": {"type": "integer", "description": "Quads per landscape section. Must be 7, 15, 31, 63, or 127.", "default": 63},
                "sections_per_component": {"type": "integer", "description": "Sections per component (1x1 or 2x2).", "default": 1},
                "num_components_x": {"type": "integer", "description": "Number of landscape components along X.", "default": 8},
                "num_components_y": {"type": "integer", "description": "Number of landscape components along Y.", "default": 8},
                "material": {"type": "string", "description": "Content path to a landscape material (e.g. '/Game/Materials/M_Landscape').", "default": ""}
            },
            "required": []
        }
    },
    {
        "name": "import_heightmap",
        "description": "Import a heightmap image (PNG/RAW 16-bit) onto an existing landscape. The file should be in the sync folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Heightmap filename in the sync folder (e.g. 'terrain_height.png')."},
                "landscape_name": {"type": "string", "description": "Label of the target Landscape actor.", "default": "Landscape"}
            },
            "required": ["filename"]
        }
    },
    {
        "name": "export_heightmap",
        "description": "Export the current landscape heightmap to a file in the sync folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "landscape_name": {"type": "string", "description": "Label of the Landscape actor to export.", "default": "Landscape"},
                "filename": {"type": "string", "description": "Output filename (e.g. 'exported_height.png').", "default": "landscape_heightmap.png"}
            },
            "required": []
        }
    },
    {
        "name": "sculpt_landscape",
        "description": "Sculpt the landscape by raising/lowering terrain at specific world coordinates. Simulates brush strokes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "points": {
                    "type": "array",
                    "description": "Array of sculpt points. Each has x, y (world coords), strength (-1.0 to 1.0 where negative = dig, positive = raise), and radius (brush size in cm).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "strength": {"type": "number", "default": 0.5},
                            "radius": {"type": "number", "default": 1000}
                        }
                    }
                },
                "landscape_name": {"type": "string", "default": "Landscape"}
            },
            "required": ["points"]
        }
    },
    {
        "name": "paint_landscape_layer",
        "description": "Paint a landscape material layer at specific world coordinates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layer_name": {"type": "string", "description": "Name of the landscape layer info to paint (e.g. 'Grass', 'Rock', 'Sand')."},
                "points": {
                    "type": "array",
                    "description": "Array of paint points with x, y (world coords), strength (0-1), and radius (brush size in cm).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "strength": {"type": "number", "default": 1.0},
                            "radius": {"type": "number", "default": 1000}
                        }
                    }
                },
                "landscape_name": {"type": "string", "default": "Landscape"}
            },
            "required": ["layer_name", "points"]
        }
    },
    {
        "name": "set_landscape_material",
        "description": "Assign a material to the landscape actor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_path": {"type": "string", "description": "Content path to the material (e.g. '/Game/Materials/M_Landscape')."},
                "landscape_name": {"type": "string", "default": "Landscape"}
            },
            "required": ["material_path"]
        }
    },
    {
        "name": "get_landscape_info",
        "description": "Get detailed info about a landscape actor: bounds, component count, material, layer info, etc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "landscape_name": {"type": "string", "default": "Landscape"}
            },
            "required": []
        }
    },
    # ── Foliage Tools ─────────────────────────────────────────────────────────
    {
        "name": "add_foliage",
        "description": "Place foliage instances (trees, grass, rocks) at specific world locations using a foliage type asset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "foliage_type": {"type": "string", "description": "Content path to a Static Mesh or Foliage Type asset (e.g. '/Game/Foliage/SM_Tree')."},
                "instances": {
                    "type": "array",
                    "description": "Array of instances. Each has location (x,y,z), rotation (pitch,yaw,roll in degrees), and scale (uniform float).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"},
                            "yaw": {"type": "number", "default": 0},
                            "pitch": {"type": "number", "default": 0},
                            "roll": {"type": "number", "default": 0},
                            "scale": {"type": "number", "default": 1.0}
                        }
                    }
                },
                "align_to_surface": {"type": "boolean", "description": "Snap foliage to terrain surface below.", "default": True}
            },
            "required": ["foliage_type", "instances"]
        }
    },
    {
        "name": "remove_foliage",
        "description": "Remove all foliage instances within a radius of a world point.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"},
                "radius": {"type": "number", "description": "Removal radius in cm.", "default": 500},
                "foliage_type": {"type": "string", "description": "Optional: only remove this specific foliage type. Leave blank to remove all.", "default": ""}
            },
            "required": ["x", "y", "z"]
        }
    },
    # ── Mesh / Modeling Tools ─────────────────────────────────────────────────
    {
        "name": "mesh_boolean",
        "description": "Perform a boolean operation (union, subtract, intersect) between two static mesh actors in the level.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_actor": {"type": "string", "description": "Label of the target (base) actor."},
                "tool_actor": {"type": "string", "description": "Label of the tool (cutter) actor."},
                "operation": {"type": "string", "description": "Boolean operation: union, subtract, or intersect.", "default": "subtract"}
            },
            "required": ["target_actor", "tool_actor"]
        }
    },
    {
        "name": "generate_mesh_from_spline",
        "description": "Create a mesh by sweeping a profile along a spline path. Great for roads, rivers, pipes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name for the generated actor."},
                "spline_points": {
                    "type": "array",
                    "description": "Array of world-space points defining the spline path.",
                    "items": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}}
                },
                "width": {"type": "number", "description": "Width of the swept profile in cm.", "default": 200},
                "closed": {"type": "boolean", "description": "Close the spline into a loop.", "default": False}
            },
            "required": ["name", "spline_points"]
        }
    },
    {
        "name": "create_pcg_component",
        "description": "Spawn a PCG component on an actor or create a new PCG Actor/Volume.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string", "description": "The exact name/label of the actor to attach PCG component. If empty, spawns a new PCG actor."},
                "graph_path": {"type": "string", "description": "Content path to PCG Graph asset to assign, e.g. '/Game/PCG/MyGraph'."},
                "location": {
                    "type": "object",
                    "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}},
                    "default": {"x": 0, "y": 0, "z": 0}
                },
                "scale": {
                    "type": "object",
                    "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}},
                    "default": {"x": 1, "y": 1, "z": 1}
                }
            },
            "required": ["graph_path"]
        }
    },
    {
        "name": "pcg_generate",
        "description": "Trigger generation on a PCG component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string", "description": "The exact name/label of the actor with the PCG component."}
            },
            "required": ["actor_name"]
        }
    },
    {
        "name": "pcg_cleanup",
        "description": "Clean up the generated resources of a PCG component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string", "description": "The exact name/label of the actor with the PCG component."}
            },
            "required": ["actor_name"]
        }
    },
    {
        "name": "pcg_set_parameter",
        "description": "Set or override a parameter on a PCG Graph Instance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string", "description": "The exact name/label of the actor with the PCG component."},
                "parameter_name": {"type": "string", "description": "Name of the parameter inside the PCG graph."},
                "value": {"description": "The value to set (int, float, bool, string, Vector object, etc.)."},
                "value_type": {"type": "string", "description": "Optional type declaration: int, float, bool, string, vector, rotator."}
            },
            "required": ["actor_name", "parameter_name", "value"]
        }
    },
    {
        "name": "pcg_get_parameters",
        "description": "Retrieve information and parameter overrides status from a PCG component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string", "description": "The exact name/label of the actor with the PCG component."}
            },
            "required": ["actor_name"]
        }
    },
    {
        "name": "align_actors",
        "description": "Precisely align actor B next to actor A along a specified axis so they touch exactly (no gap, no overlap). Great for walls/grids.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_a_name": {"type": "string", "description": "Reference actor name."},
                "actor_b_name": {"type": "string", "description": "Actor to move name."},
                "axis": {"type": "string", "description": "Alignment axis: +X, -X, +Y, -Y, +Z, -Z.", "default": "+X"},
                "offset": {"type": "number", "description": "Optional spacing distance in cm (positive for gap, negative for overlap).", "default": 0.0}
            },
            "required": ["actor_a_name", "actor_b_name"]
        }
    },
    {
        "name": "get_actor_dimensions",
        "description": "Get world-space bounding box size (in cm), origin, and min/max extents of any actor. Use BEFORE placing adjacent actors to measure correctly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string", "description": "The exact label of the actor to measure."}
            },
            "required": ["actor_name"]
        }
    },
    {
        "name": "snap_to_grid",
        "description": "Snap an actor's location to the nearest grid unit so placement is always on exact coordinates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string", "description": "The exact label of the actor to snap."},
                "grid_size": {"type": "number", "description": "Grid unit size in cm (e.g. 100 = 1 meter).", "default": 100.0}
            },
            "required": ["actor_name"]
        }
    },
    {
        "name": "verify_actor_alignment",
        "description": "Check if two actors are touching perfectly, overlapping, or have a gap. Always call this after align_actors to confirm correctness.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_a_name": {"type": "string", "description": "First actor name."},
                "actor_b_name": {"type": "string", "description": "Second actor name."},
                "axis": {"type": "string", "description": "Axis to check: X, Y, or Z.", "default": "X"}
            },
            "required": ["actor_a_name", "actor_b_name"]
        }
    },
    {
        "name": "create_blueprint_class",
        "description": "Create a new Blueprint class asset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "class_name": {"type": "string"},
                "parent_class": {"type": "string", "default": "Actor"},
                "save_path": {"type": "string", "default": "/Game/Blueprints"}
            },
            "required": ["class_name"]
        }
    },
    {
        "name": "compile_blueprint",
        "description": "Compile a Blueprint asset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "blueprint_path": {"type": "string"}
            },
            "required": ["blueprint_path"]
        }
    },
    {
        "name": "add_blueprint_component",
        "description": "Add a component to a Blueprint class.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "blueprint_path": {"type": "string"},
                "component_class": {"type": "string", "description": "e.g. StaticMeshComponent"},
                "component_name": {"type": "string"}
            },
            "required": ["blueprint_path", "component_class", "component_name"]
        }
    },
    {
        "name": "set_blueprint_default_value",
        "description": "Set a default value for a property in a Blueprint's CDO.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "blueprint_path": {"type": "string"},
                "property_name": {"type": "string"},
                "property_value": {"type": "string", "description": "String representation of the value"}
            },
            "required": ["blueprint_path", "property_name", "property_value"]
        }
    },
    {
        "name": "reparent_blueprint",
        "description": "Reparent a Blueprint to a new class.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "blueprint_path": {"type": "string"},
                "new_parent_class": {"type": "string"}
            },
            "required": ["blueprint_path", "new_parent_class"]
        }
    },
    {
        "name": "get_blueprint_info",
        "description": "Get information about a Blueprint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "blueprint_path": {"type": "string"}
            },
            "required": ["blueprint_path"]
        }
    },
    {
        "name": "create_material_asset",
        "description": "Create a new Material asset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string"},
                "save_path": {"type": "string", "default": "/Game/Materials"}
            },
            "required": ["material_name"]
        }
    },
    {
        "name": "create_material_instance",
        "description": "Create a new Material Instance Constant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "instance_name": {"type": "string"},
                "parent_path": {"type": "string"},
                "save_path": {"type": "string", "default": "/Game/Materials"}
            },
            "required": ["instance_name", "parent_path"]
        }
    },
    {
        "name": "set_material_scalar_param",
        "description": "Set a scalar parameter on a material instance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_instance_path": {"type": "string"},
                "param_name": {"type": "string"},
                "value": {"type": "number"}
            },
            "required": ["material_instance_path", "param_name", "value"]
        }
    },
    {
        "name": "set_material_vector_param",
        "description": "Set a vector parameter on a material instance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_instance_path": {"type": "string"},
                "param_name": {"type": "string"},
                "r": {"type": "number"},
                "g": {"type": "number"},
                "b": {"type": "number"},
                "a": {"type": "number", "default": 1.0}
            },
            "required": ["material_instance_path", "param_name", "r", "g", "b"]
        }
    },
    {
        "name": "set_material_texture_param",
        "description": "Set a texture parameter on a material instance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_instance_path": {"type": "string"},
                "param_name": {"type": "string"},
                "texture_path": {"type": "string"}
            },
            "required": ["material_instance_path", "param_name", "texture_path"]
        }
    },
    {
        "name": "set_nanite_enabled",
        "description": "Enable or disable Nanite on a static mesh.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mesh_path": {"type": "string"},
                "enabled": {"type": "boolean", "default": True}
            },
            "required": ["mesh_path", "enabled"]
        }
    },
    {
        "name": "set_actor_material",
        "description": "Set the material on an actor's StaticMeshComponent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "material_path": {"type": "string"},
                "slot_index": {"type": "integer", "default": 0}
            },
            "required": ["actor_name", "material_path"]
        }
    },
    {
        "name": "apply_lumen_settings",
        "description": "Enable or disable Lumen GI and Reflections.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "enable_gi": {"type": "boolean", "default": True},
                "enable_reflections": {"type": "boolean", "default": True}
            },
            "required": []
        }
    },
    {
        "name": "create_level_sequence",
        "description": "Create a new Level Sequence asset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sequence_name": {"type": "string"},
                "save_path": {"type": "string", "default": "/Game/Sequences"},
                "duration_seconds": {"type": "number", "default": 5.0}
            },
            "required": ["sequence_name"]
        }
    },
    {
        "name": "add_actor_to_sequence",
        "description": "Add an actor to a level sequence as a possessable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sequence_path": {"type": "string"},
                "actor_name": {"type": "string"}
            },
            "required": ["sequence_path", "actor_name"]
        }
    },
    {
        "name": "open_level_sequence",
        "description": "Open a level sequence in the editor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sequence_path": {"type": "string"}
            },
            "required": ["sequence_path"]
        }
    },
    {
        "name": "set_sequence_length",
        "description": "Set the playback length and FPS of a level sequence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sequence_path": {"type": "string"},
                "start_frame": {"type": "integer", "default": 0},
                "end_frame": {"type": "integer", "default": 150},
                "fps": {"type": "integer", "default": 30}
            },
            "required": ["sequence_path"]
        }
    },
    {
        "name": "spawn_niagara_system",
        "description": "Spawn a Niagara system actor in the level.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "system_path": {"type": "string"},
                "actor_name": {"type": "string"},
                "x": {"type": "number"},
                "y": {"type": "number"},
                "z": {"type": "number"}
            },
            "required": ["system_path", "actor_name", "x", "y", "z"]
        }
    },
    {
        "name": "set_niagara_float",
        "description": "Set a float user variable on a Niagara actor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "variable_name": {"type": "string"},
                "value": {"type": "number"}
            },
            "required": ["actor_name", "variable_name", "value"]
        }
    },
    {
        "name": "set_niagara_bool",
        "description": "Set a bool user variable on a Niagara actor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "variable_name": {"type": "string"},
                "value": {"type": "boolean"}
            },
            "required": ["actor_name", "variable_name", "value"]
        }
    },
    {
        "name": "set_niagara_vector",
        "description": "Set a vector user variable on a Niagara actor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "variable_name": {"type": "string"},
                "x": {"type": "number"},
                "y": {"type": "number"},
                "z": {"type": "number"}
            },
            "required": ["actor_name", "variable_name", "x", "y", "z"]
        }
    },
    {
        "name": "run_console_command",
        "description": "Run an Unreal console command.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "save_current_level",
        "description": "Save the current editor level.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "set_world_gravity",
        "description": "Set the global gravity Z setting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "gravity_z": {"type": "number", "default": -980.0}
            },
            "required": []
        }
    },
    {
        "name": "spawn_sky_atmosphere",
        "description": "Spawn a SkyAtmosphere actor.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "spawn_directional_light",
        "description": "Spawn a Directional Light actor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "intensity": {"type": "number", "default": 10.0},
                "pitch": {"type": "number", "default": -45.0},
                "yaw": {"type": "number", "default": 0.0}
            },
            "required": ["actor_name"]
        }
    },
    {
        "name": "spawn_exponential_fog",
        "description": "Spawn an Exponential Height Fog actor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "fog_density": {"type": "number", "default": 0.02},
                "start_distance": {"type": "number", "default": 0.0}
            },
            "required": ["actor_name"]
        }
    },
    {
        "name": "create_post_process_volume",
        "description": "Spawn a Post Process Volume.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "is_unbound": {"type": "boolean", "default": True}
            },
            "required": ["actor_name"]
        }
    },
    {
        "name": "list_assets_by_class",
        "description": "List all assets of a specific class.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "asset_class": {"type": "string", "description": "e.g. 'StaticMesh'"},
                "search_path": {"type": "string", "default": "/Game"}
            },
            "required": ["asset_class"]
        }
    },
    {
        "name": "duplicate_asset",
        "description": "Duplicate an asset to a new path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_path": {"type": "string"},
                "new_path": {"type": "string"}
            },
            "required": ["source_path", "new_path"]
        }
    },
    {
        "name": "delete_asset",
        "description": "Delete an asset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "asset_path": {"type": "string"}
            },
            "required": ["asset_path"]
        }
    },
    {
        "name": "rename_asset",
        "description": "Rename or move an asset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_path": {"type": "string"},
                "destination_path": {"type": "string"}
            },
            "required": ["source_path", "destination_path"]
        }
    },
    {
        "name": "find_actors_by_tag",
        "description": "Find all actors matching a specific tag.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tag": {"type": "string"}
            },
            "required": ["tag"]
        }
    },
    {
        "name": "set_actor_tag",
        "description": "Add a tag to an actor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "tag": {"type": "string"}
            },
            "required": ["actor_name", "tag"]
        }
    },
    {
        "name": "create_content_folder",
        "description": "Create a new folder in the Content Browser.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder_path": {"type": "string"}
            },
            "required": ["folder_path"]
        }
    },
    {
        "name": "set_actor_physics",
        "description": "Enable or disable physics simulation on an actor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "enabled": {"type": "boolean"},
                "gravity_enabled": {"type": "boolean", "default": True}
            },
            "required": ["actor_name", "enabled"]
        }
    },
    {
        "name": "set_collision_profile",
        "description": "Set the collision profile on an actor's primitive components.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "profile_name": {"type": "string"}
            },
            "required": ["actor_name", "profile_name"]
        }
    },
    {
        "name": "generate_mesh_collision",
        "description": "Generate simple collision for a static mesh.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mesh_path": {"type": "string"},
                "method": {"type": "string", "description": "box, sphere, capsule, complex_as_simple, convex"}
            },
            "required": ["mesh_path", "method"]
        }
    },
    {
        "name": "remove_mesh_collision",
        "description": "Remove all collision from a static mesh.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mesh_path": {"type": "string"}
            },
            "required": ["mesh_path"]
        }
    },
    {
        "name": "set_actor_mass",
        "description": "Override and set the mass (kg) on an actor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string"},
                "mass_kg": {"type": "number"}
            },
            "required": ["actor_name", "mass_kg"]
        }
    }
]

# --------------------------------------------------------------------------
# Send a request to the Unreal socket server
# --------------------------------------------------------------------------
def call_unreal(action: str, extra: dict) -> dict:
    payload = {"auth_token": AUTH_TOKEN, "action": action, **extra}
    raw = json.dumps(payload).encode("utf-8")
    try:
        with socket.create_connection((UNREAL_HOST, UNREAL_PORT), timeout=10) as sock:
            sock.sendall(raw)
            sock.shutdown(socket.SHUT_WR)  # Signal EOF so server stops reading
            # Read response (up to 1 MB)
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            response_raw = b"".join(chunks).decode("utf-8", errors="replace")
            
            if not response_raw.strip():
                return {"status": "error", "message": "Empty response received from socket server."}
                
            try:
                return json.loads(response_raw)
            except json.JSONDecodeError as e:
                import sys
                print(f"RAW RESPONSE ERROR: {repr(response_raw)}", file=sys.stderr)
                return {"status": "error", "message": f"Invalid JSON from socket server: {str(e)}"}
    except ConnectionRefusedError:
        return {"status": "error", "message": f"Cannot connect to Unreal on port {UNREAL_PORT}. Is the editor running with the plugin loaded?"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

# --------------------------------------------------------------------------
# MCP JSON-RPC helpers
# --------------------------------------------------------------------------
def send(obj: dict):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def error_response(req_id, code: int, message: str):
    send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})

# --------------------------------------------------------------------------
# Handle individual tool calls
# --------------------------------------------------------------------------
def handle_tool(name: str, args: dict) -> list:
    """Map MCP tool name -> Unreal action, call, return result as list of content blocks."""
    if name == "get_actor_hierarchy":
        result = call_unreal("get_actor_hierarchy", {})
    elif name == "create_actor":
        result = call_unreal("create_actor", args)
    elif name == "delete_actor":
        result = call_unreal("delete_actor", args)
    elif name == "set_transform":
        result = call_unreal("set_transform", args)
    elif name == "trigger_sync":
        result = call_unreal("trigger_sync", args)
    elif name == "get_metadata":
        result = call_unreal("get_metadata", {})
    elif name == "set_metadata":
        result = call_unreal("set_metadata", args)
    elif name == "get_asset_hierarchy":
        result = call_unreal("get_asset_hierarchy", {})
    elif name == "run_editor_command":
        result = call_unreal("run_editor_command", args)
    elif name == "get_actor_property":
        result = call_unreal("get_actor_property", args)
    elif name == "set_actor_property":
        result = call_unreal("set_actor_property", args)
    elif name == "call_blueprint_function":
        result = call_unreal("call_blueprint_function", args)
    elif name == "execute_unreal_python":
        result = call_unreal("execute_unreal_python", args)
    elif name == "take_screenshot":
        result = call_unreal("take_screenshot", {})
        if isinstance(result, dict) and "image_data" in result:
            return [{"type": "image", "data": result["image_data"], "mimeType": "image/png"}]
    elif name == "spawn_blockout_primitive":
        result = call_unreal("spawn_blockout_primitive", args)
    elif name == "batch_create_actors":
        actors = args.get("actors", [])
        results = []
        for actor_def in actors:
            r = call_unreal("spawn_blockout_primitive", actor_def)
            results.append(r)
        result = {"status": "ok", "created": len(results), "results": results}
    elif name == "import_fbx":
        result = call_unreal("import_fbx", args)
    elif name in ("create_landscape", "import_heightmap", "export_heightmap",
                  "sculpt_landscape", "paint_landscape_layer", "set_landscape_material",
                  "get_landscape_info", "add_foliage", "remove_foliage",
                  "mesh_boolean", "generate_mesh_from_spline",
                  "create_pcg_component", "pcg_generate", "pcg_cleanup",
                  "pcg_set_parameter", "pcg_get_parameters",
                  "align_actors", "get_actor_dimensions", "snap_to_grid", "verify_actor_alignment",
                  "create_blueprint_class", "compile_blueprint", "add_blueprint_component", 
                  "set_blueprint_default_value", "reparent_blueprint", "get_blueprint_info",
                  "create_material_asset", "create_material_instance", "set_material_scalar_param", 
                  "set_material_vector_param", "set_material_texture_param", "set_nanite_enabled", 
                  "set_actor_material", "apply_lumen_settings", "create_level_sequence", 
                  "add_actor_to_sequence", "open_level_sequence", "set_sequence_length", 
                  "spawn_niagara_system", "set_niagara_float", "set_niagara_bool", 
                  "set_niagara_vector", "run_console_command", "save_current_level", 
                  "set_world_gravity", "spawn_sky_atmosphere", "spawn_directional_light", 
                  "spawn_exponential_fog", "create_post_process_volume", "list_assets_by_class", 
                  "duplicate_asset", "delete_asset", "rename_asset", "find_actors_by_tag", 
                  "set_actor_tag", "create_content_folder", "set_actor_physics", 
                  "set_collision_profile", "generate_mesh_collision", "remove_mesh_collision", 
                  "set_actor_mass"):
        result = call_unreal(name, args)
    else:
        result = {"status": "error", "message": f"Unknown tool: {name}"}

    res_str = json.dumps(result, indent=2)
    if len(res_str) > 800000:
        res_str = res_str[:800000] + "\n... [Output truncated to stay under 1MB Claude Desktop limit]"
    return [{"type": "text", "text": res_str}]

# --------------------------------------------------------------------------
# Main stdio loop
# --------------------------------------------------------------------------
def main():
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        method = req.get("method", "")
        req_id = req.get("id")
        params = req.get("params", {})

        # ---- Handshake ----
        if method == "initialize":
            send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "UnrealMCPBridge", "version": "1.0.0"}
                }
            })

        elif method == "notifications/initialized":
            pass   # no response needed

        # ---- Tool listing ----
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})

        # ---- Tool execution ----
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args  = params.get("arguments", {})
            try:
                content = handle_tool(tool_name, tool_args)
                send({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": content,
                        "isError": False
                    }
                })
            except Exception:
                error_response(req_id, -32000, traceback.format_exc())

        else:
            # Unknown method – return empty result so client doesn't hang
            send({"jsonrpc": "2.0", "id": req_id, "result": {}})

if __name__ == "__main__":
    main()
