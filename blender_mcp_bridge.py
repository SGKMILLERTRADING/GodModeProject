"""
Blender MCP Bridge
------------------
This script is a proper MCP server (stdio transport) for Claude Desktop, LM Studio, etc.
It translates MCP tool calls -> TCP socket requests -> Blender AI Bridge (port 12345).

HOW IT WORKS:
  AI client launches this script via stdio.
  This script listens for JSON-RPC messages on stdin, forwards them to
  Blender on 127.0.0.1:12345, and writes the response to stdout.
"""

import sys
import json
import socket
import traceback

BLENDER_HOST = "127.0.0.1"
BLENDER_PORT = 12345

TOOLS = [
    {
        "name": "get_scene_hierarchy",
        "description": "List all objects in the current Blender scene.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "create_primitive",
        "description": "Spawn a primitive (Cube, Sphere, Cylinder, etc) in Blender.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "CUBE, SPHERE, CYLINDER, PLANE, CONE", "default": "CUBE"},
                "name": {"type": "string", "description": "Optional name for the object"},
                "size": {"type": "number", "default": 2.0},
                "location": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "[x, y, z] location"
                }
            }
        }
    },
    {
        "name": "batch_create_blockout",
        "description": "Create multiple primitive objects at once in Blender.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "primitives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "name": {"type": "string"},
                            "location": {"type": "array", "items": {"type": "number"}},
                            "scale": {"type": "array", "items": {"type": "number"}},
                            "rotation": {"type": "array", "items": {"type": "number"}, "description": "Euler degrees"}
                        }
                    }
                }
            },
            "required": ["primitives"]
        }
    },
    {
        "name": "delete_object",
        "description": "Delete an object by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "set_transform",
        "description": "Set location, rotation (degrees), or scale of an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "location": {"type": "array", "items": {"type": "number"}},
                "rotation": {"type": "array", "items": {"type": "number"}},
                "scale": {"type": "array", "items": {"type": "number"}}
            },
            "required": ["name"]
        }
    },
    {
        "name": "run_auto_rig",
        "description": "Rig a mesh to an armature using automatic weights in Blender.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mesh": {"type": "string", "description": "Name of the mesh object"},
                "armature": {"type": "string", "description": "Optional name of the armature (uses first found if omitted)"}
            },
            "required": ["mesh"]
        }
    },
    {
        "name": "get_bone_hierarchy",
        "description": "Read the full bone hierarchy of a Blender armature.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "armature": {"type": "string", "description": "Optional name of the armature"}
            }
        }
    },
    {
        "name": "generate_retarget_map",
        "description": "Save a bone mapping dictionary to a JSON file for Unreal retargeting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bone_map": {"type": "object", "description": "Dictionary mapping source bones to target bones"},
                "source_rig": {"type": "string", "default": "custom"},
                "target_rig": {"type": "string", "default": "UE5_Mannequin"}
            },
            "required": ["bone_map"]
        }
    },
    {
        "name": "trigger_sync",
        "description": "Trigger an export to Unreal.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "ALL, MESH, ANIM", "default": "ALL"}
            }
        }
    },
    {
        "name": "execute_python",
        "description": "God Mode: Run a Python script directly inside Blender's context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": {"type": "string"}
            },
            "required": ["script"]
        }
    },
    {
        "name": "take_screenshot",
        "description": "Take a viewport screenshot of the current Blender scene and return it as an image.",
        "inputSchema": {
            "type": "object",
            "properties": {}
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
        "description": "Trigger generation on a PCG component in Unreal.",
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
        "description": "Clean up the generated resources of a PCG component in Unreal.",
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
        "description": "Set or override a parameter on a PCG Graph Instance in Unreal.",
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
        "description": "Retrieve information and parameter overrides status from a PCG component in Unreal.",
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
        "description": "Precisely align actor B next to actor A along a specified axis in Unreal so they touch exactly (no gap, no overlap). Great for walls/grids.",
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
        "description": "Get the world-space bounding box dimensions (size in cm) and bounds origin of an actor. Use this to measure an actor before placing adjacent ones.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string", "description": "The exact name/label of the actor."}
            },
            "required": ["actor_name"]
        }
    },
    {
        "name": "snap_to_grid",
        "description": "Snap an actor's location to the nearest grid unit. Ensures perfect alignment to a grid.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_name": {"type": "string", "description": "The exact name/label of the actor."},
                "grid_size": {"type": "number", "description": "Grid unit size in cm (e.g. 100 = 1 meter).", "default": 100.0}
            },
            "required": ["actor_name"]
        }
    },
    {
        "name": "verify_actor_alignment",
        "description": "Check whether two actors are touching, overlapping, or have a gap. Returns exact distance and status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_a_name": {"type": "string", "description": "First actor name."},
                "actor_b_name": {"type": "string", "description": "Second actor name."},
                "axis": {"type": "string", "description": "Which axis to check: X, Y, or Z.", "default": "X"}
            },
            "required": ["actor_a_name", "actor_b_name"]
        }
    },
    {
        "name": "check_project_plans",
        "description": "Reads AI_Plans/{project_name}/plans.json from Dropbox.",
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
        "name": "register_active_task",
        "description": "Adds a PLANNED/IN_PROGRESS entry to plans.json.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "dropbox_path": {"type": "string"},
                "task_id": {"type": "string"},
                "author": {"type": "string"},
                "engine": {"type": "string"},
                "task_description": {"type": "string"},
                "location": {"type": "string"}
            },
            "required": ["project_name", "dropbox_path", "task_id", "author", "engine", "task_description", "location"]
        }
    },
    {
        "name": "complete_active_task",
        "description": "Marks task DONE.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "dropbox_path": {"type": "string"},
                "task_id": {"type": "string"},
                "status": {"type": "string"},
                "notes": {"type": "string"},
                "assets": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["project_name", "dropbox_path", "task_id", "status", "notes", "assets"]
        }
    },
    {
        "name": "apply_animation_to_character",
        "description": "Import an FBX/BVH animation and apply it to an armature in Blender.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "target_object": {"type": "string", "default": ""}
            },
            "required": ["filepath"]
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
    # ── Additional Blender tools not in original schema ──────────────────────
    {
        "name": "create_material",
        "description": "Create a PBR material in Blender. color is [R, G, B, A] with values 0.0-1.0.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "color": {"type": "array", "items": {"type": "number"}, "default": [1.0, 1.0, 1.0, 1.0]},
                "metallic": {"type": "number", "default": 0.0},
                "roughness": {"type": "number", "default": 0.5}
            },
            "required": ["name"]
        }
    },
    {
        "name": "set_object_material",
        "description": "Assign an existing material to an object in Blender. Both must already exist in the scene.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "object": {"type": "string", "description": "Object name"},
                "material": {"type": "string", "description": "Material name"}
            },
            "required": ["object", "material"]
        }
    },
    {
        "name": "get_object_info",
        "description": "Get detailed info (location, rotation, scale, materials) about a specific object in Blender.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "rename_object",
        "description": "Rename an object in the active Blender scene.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "old_name": {"type": "string"},
                "new_name": {"type": "string"}
            },
            "required": ["old_name", "new_name"]
        }
    },
    {
        "name": "set_keyframe",
        "description": "Insert a keyframe on an object at a specific frame in Blender.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "frame": {"type": "integer", "default": 1},
                "data_path": {"type": "string", "description": "location, rotation_euler, or scale", "default": "location"}
            },
            "required": ["name", "frame"]
        }
    },
    {
        "name": "set_timeline",
        "description": "Set the scene timeline start/end frames and FPS in Blender.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "integer", "default": 1},
                "end": {"type": "integer", "default": 250},
                "fps": {"type": "integer", "default": 24}
            }
        }
    },
    {
        "name": "render_frame",
        "description": "Render a single frame in Blender and save it to disk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "default": "//render.png"},
                "frame": {"type": "integer", "default": 1}
            }
        }
    },
    {
        "name": "set_render_settings",
        "description": "Configure render settings in Blender. engine can be CYCLES or BLENDER_EEVEE.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resolution_x": {"type": "integer"},
                "resolution_y": {"type": "integer"},
                "engine": {"type": "string"},
                "samples": {"type": "integer"}
            }
        }
    },
    {
        "name": "add_light",
        "description": "Add a light to the Blender scene. light_type: POINT, SUN, SPOT, AREA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": "NewLight"},
                "light_type": {"type": "string", "default": "POINT"},
                "location": {"type": "array", "items": {"type": "number"}, "default": [0,0,5]},
                "energy": {"type": "number", "default": 1000.0},
                "color": {"type": "array", "items": {"type": "number"}, "default": [1.0, 1.0, 1.0]}
            }
        }
    },
    {
        "name": "create_geometry_nodes_modifier",
        "description": "Create a geometry nodes modifier on an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "group_name": {"type": "string", "default": "GeometryNodes"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "add_geometry_node",
        "description": "Add a node to a geometry node group.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"},
                "node_type": {"type": "string"},
                "node_name": {"type": "string"},
                "location_x": {"type": "number", "default": 0},
                "location_y": {"type": "number", "default": 0}
            },
            "required": ["group_name", "node_type"]
        }
    },
    {
        "name": "link_geometry_nodes",
        "description": "Link two geometry nodes together.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"},
                "from_node": {"type": "string"},
                "to_node": {"type": "string"},
                "from_socket": {"type": "integer", "default": 0},
                "to_socket": {"type": "integer", "default": 0}
            },
            "required": ["group_name", "from_node", "to_node"]
        }
    },
    {
        "name": "set_geometry_node_value",
        "description": "Set a value on a geometry node's input socket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"},
                "node_name": {"type": "string"},
                "value": {},
                "socket_index": {"type": "integer", "default": 0}
            },
            "required": ["group_name", "node_name", "value"]
        }
    },
    {
        "name": "list_geometry_nodes",
        "description": "List all nodes in a geometry node group.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"}
            },
            "required": ["group_name"]
        }
    },
    {
        "name": "add_modifier",
        "description": "Add a modifier to an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "modifier_type": {"type": "string", "default": "SUBSURF"},
                "modifier_name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "remove_modifier",
        "description": "Remove a modifier from an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "modifier_name": {"type": "string"}
            },
            "required": ["name", "modifier_name"]
        }
    },
    {
        "name": "apply_modifier",
        "description": "Apply a modifier on an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "modifier_name": {"type": "string"}
            },
            "required": ["name", "modifier_name"]
        }
    },
    {
        "name": "set_modifier_property",
        "description": "Set a property on a modifier.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "modifier_name": {"type": "string"},
                "property_name": {"type": "string"},
                "value": {}
            },
            "required": ["name", "modifier_name", "property_name", "value"]
        }
    },
    {
        "name": "list_modifiers",
        "description": "List modifiers on an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "uv_unwrap",
        "description": "UV Unwrap an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "method": {"type": "string", "default": "smart"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "pack_uv_islands",
        "description": "Pack UV islands for an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_image_texture",
        "description": "Create a new image texture in Blender.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_name": {"type": "string", "default": "NewImage"},
                "width": {"type": "integer", "default": 1024},
                "height": {"type": "integer", "default": 1024},
                "color": {"type": "array", "items": {"type": "number"}, "default": [0.0, 0.0, 0.0, 1.0]}
            }
        }
    },
    {
        "name": "save_image",
        "description": "Save an image texture to disk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_name": {"type": "string"},
                "filepath": {"type": "string"}
            },
            "required": ["image_name", "filepath"]
        }
    },
    {
        "name": "add_shader_node",
        "description": "Add a shader node to a material.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string"},
                "node_type": {"type": "string"},
                "node_name": {"type": "string"},
                "location_x": {"type": "number", "default": 0},
                "location_y": {"type": "number", "default": 0}
            },
            "required": ["material_name", "node_type"]
        }
    },
    {
        "name": "link_shader_nodes",
        "description": "Link shader nodes together.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string"},
                "from_node": {"type": "string"},
                "to_node": {"type": "string"},
                "from_socket": {"type": "integer", "default": 0},
                "to_socket": {"type": "integer", "default": 0}
            },
            "required": ["material_name", "from_node", "to_node"]
        }
    },
    {
        "name": "set_shader_node_value",
        "description": "Set a value on a shader node socket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string"},
                "node_name": {"type": "string"},
                "value": {},
                "socket_index": {"type": "integer", "default": 0}
            },
            "required": ["material_name", "node_name", "value"]
        }
    },
    {
        "name": "create_full_pbr_material",
        "description": "Create a full PBR material with standard inputs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string", "default": "NewPBRMaterial"},
                "base_color": {"type": "array", "items": {"type": "number"}, "default": [0.8, 0.8, 0.8, 1.0]},
                "metallic": {"type": "number", "default": 0.0},
                "roughness": {"type": "number", "default": 0.5},
                "emission_strength": {"type": "number", "default": 0.0}
            }
        }
    },
    {
        "name": "get_material_nodes",
        "description": "List all nodes in a material.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_name": {"type": "string"}
            },
            "required": ["material_name"]
        }
    },
    {
        "name": "export_fbx",
        "description": "Export the scene to FBX.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "selected_only": {"type": "boolean", "default": False},
                "scale_factor": {"type": "number", "default": 1.0}
            }
        }
    },
    {
        "name": "export_gltf",
        "description": "Export the scene to GLTF/GLB.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "format": {"type": "string", "default": "GLB"},
                "selected_only": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "name": "export_obj",
        "description": "Export the scene to OBJ.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "selected_only": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "name": "import_obj",
        "description": "Import an OBJ file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"}
            },
            "required": ["filepath"]
        }
    },
    {
        "name": "import_gltf",
        "description": "Import a GLTF/GLB file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"}
            },
            "required": ["filepath"]
        }
    },
    {
        "name": "export_alembic",
        "description": "Export the scene to Alembic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "start_frame": {"type": "integer"},
                "end_frame": {"type": "integer"}
            }
        }
    },
    {
        "name": "create_action",
        "description": "Create a new animation action for an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "action_name": {"type": "string", "default": "NewAction"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "push_to_nla",
        "description": "Push the active action to a new NLA track.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "track_name": {"type": "string", "default": "NLATrack"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "clear_animation",
        "description": "Clear all animation data from an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "set_bone_pose_rotation",
        "description": "Set a bone's pose rotation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "armature_name": {"type": "string"},
                "bone_name": {"type": "string"},
                "rotation_mode": {"type": "string", "default": "QUATERNION"},
                "values": {"type": "array", "items": {"type": "number"}, "default": [1, 0, 0, 0]}
            },
            "required": ["armature_name", "bone_name"]
        }
    },
    {
        "name": "add_rigid_body",
        "description": "Add a rigid body to an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "rb_type": {"type": "string", "default": "ACTIVE"},
                "mass": {"type": "number", "default": 1.0}
            },
            "required": ["name"]
        }
    },
    {
        "name": "add_cloth_simulation",
        "description": "Add cloth simulation to an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "add_particle_system",
        "description": "Add a particle system to an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "particle_type": {"type": "string", "default": "EMITTER"},
                "count": {"type": "integer", "default": 1000},
                "lifetime": {"type": "integer", "default": 50}
            },
            "required": ["name"]
        }
    },
    {
        "name": "bake_physics",
        "description": "Bake all physics caches.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "setup_compositor",
        "description": "Setup basic compositor nodes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "default": "//compositor_output/"}
            }
        }
    },
    {
        "name": "add_compositor_node",
        "description": "Add a compositor node.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_type": {"type": "string"},
                "node_name": {"type": "string"},
                "location_x": {"type": "number", "default": 0},
                "location_y": {"type": "number", "default": 0}
            },
            "required": ["node_type"]
        }
    },
    {
        "name": "link_compositor_nodes",
        "description": "Link two compositor nodes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_node": {"type": "string"},
                "to_node": {"type": "string"},
                "from_socket": {"type": "integer", "default": 0},
                "to_socket": {"type": "integer", "default": 0}
            },
            "required": ["from_node", "to_node"]
        }
    },
    {
        "name": "set_render_pass",
        "description": "Enable a specific render pass.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pass_name": {"type": "string", "default": "ao"}
            }
        }
    },
    {
        "name": "duplicate_object",
        "description": "Duplicate an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "new_name": {"type": "string"},
                "offset_x": {"type": "number", "default": 0},
                "offset_y": {"type": "number", "default": 0},
                "offset_z": {"type": "number", "default": 0}
            },
            "required": ["name"]
        }
    },
    {
        "name": "select_objects_by_type",
        "description": "Select objects by type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "object_type": {"type": "string", "default": "MESH"}
            }
        }
    },
    {
        "name": "join_objects",
        "description": "Join multiple objects into one.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "object_names": {"type": "array", "items": {"type": "string"}},
                "result_name": {"type": "string"}
            },
            "required": ["object_names"]
        }
    },
    {
        "name": "set_origin",
        "description": "Set the origin of an object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "origin_type": {"type": "string", "default": "ORIGIN_CENTER_OF_MASS"}
            },
            "required": ["name"]
        }
    }
]


def call_blender(action: str, extra: dict) -> dict:
    payload = {"action": action, **extra}
    raw = json.dumps(payload).encode("utf-8")
    try:
        with socket.create_connection((BLENDER_HOST, BLENDER_PORT), timeout=60) as sock:
            sock.sendall(raw)
            # Signal end of transmission by shutting down write half (if server expects it, otherwise just read)
            sock.shutdown(socket.SHUT_WR)
            
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            response_raw = b"".join(chunks).decode("utf-8", errors="replace")
            
            if not response_raw.strip():
                return {"status": "error", "message": "Empty response"}
                
            try:
                return json.loads(response_raw)
            except json.JSONDecodeError as e:
                print(f"RAW RESPONSE ERROR: {repr(response_raw)}", file=sys.stderr)
                return {"status": "error", "message": str(e)}
    except ConnectionRefusedError:
        return {"status": "error", "message": "Cannot connect to Blender on port 12345. Make sure the AI Bridge is running in the Blender addon."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def send(obj: dict):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def error_response(req_id, code: int, message: str):
    send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


UNREAL_HOST = "127.0.0.1"
UNREAL_PORT = 8001
AUTH_TOKEN = "d9a7f3e8b6c04a92a5f2e1c4b9d7e3a1"

# All tools that should be routed to Unreal instead of Blender
_UNREAL_TOOLS = frozenset([
    "get_actor_hierarchy", "create_actor", "delete_actor", "set_transform",
    "trigger_sync", "get_metadata", "set_metadata", "get_asset_hierarchy",
    "run_editor_command", "get_actor_property", "set_actor_property",
    "call_blueprint_function", "execute_unreal_python", "take_screenshot",
    "spawn_blockout_primitive", "batch_create_actors", "import_fbx",
    "create_landscape", "import_heightmap", "export_heightmap",
    "sculpt_landscape", "paint_landscape_layer", "set_landscape_material",
    "get_landscape_info", "add_foliage", "remove_foliage",
    "mesh_boolean", "generate_mesh_from_spline",
    "create_pcg_component", "pcg_generate", "pcg_cleanup",
    "pcg_set_parameter", "pcg_get_parameters",
    "align_actors", "get_actor_dimensions", "snap_to_grid", "verify_actor_alignment",
])

def call_unreal(action: str, extra: dict) -> dict:
    payload = {"auth_token": AUTH_TOKEN, "action": action, **extra}
    raw = json.dumps(payload).encode("utf-8")
    try:
        with socket.create_connection((UNREAL_HOST, UNREAL_PORT), timeout=10) as sock:
            sock.sendall(raw)
            sock.shutdown(socket.SHUT_WR)  # Signal EOF so server stops reading
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            response_raw = b"".join(chunks).decode("utf-8", errors="replace")
            if not response_raw.strip():
                return {"status": "error", "message": "Empty response from Unreal"}
            return json.loads(response_raw)
    except Exception as exc:
        return {"status": "error", "message": f"Unreal connection error: {str(exc)}"}


def handle_tool(name: str, args: dict) -> list:
    """Map MCP tool name -> Blender or Unreal action"""
    if name in _UNREAL_TOOLS:
        result = call_unreal(name, args)
    else:
        result = call_blender(name, args)
    if name == "take_screenshot" and isinstance(result, dict) and "image_data" in result:
        return [{"type": "image", "data": result["image_data"], "mimeType": "image/png"}]
    res_str = json.dumps(result, indent=2)
    if len(res_str) > 800000:
        res_str = res_str[:800000] + "\n... [Output truncated to stay under 1MB Claude Desktop limit]"
    return [{"type": "text", "text": res_str}]


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

        if method == "initialize":
            send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "BlenderMCPBridge", "version": "1.0.0"}
                }
            })
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
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
            send({"jsonrpc": "2.0", "id": req_id, "result": {}})

if __name__ == "__main__":
    main()
