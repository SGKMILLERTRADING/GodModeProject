import unreal
import socket
import threading
import json
import queue

UDP_IP = "127.0.0.1"
UDP_PORT = 8002

_receiver_thread = None
_stop_event = threading.Event()
_update_queue = queue.Queue()
_tick_handle = None

def udp_listener():
    """Background thread to listen for UDP packets."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(1.0)
    
    unreal.log(f"Unreal Live Link Receiver listening on {UDP_IP}:{UDP_PORT}...")
    
    while not _stop_event.is_set():
        try:
            data, addr = sock.recvfrom(65535)
            payload = json.loads(data.decode('utf-8'))
            if payload.get("action") == "livelink_update":
                _update_queue.put(payload.get("objects", []))
        except socket.timeout:
            continue
        except json.JSONDecodeError:
            pass
        except Exception as e:
            if not _stop_event.is_set():
                unreal.log_warning(f"Live Link UDP Error: {e}")
                
    sock.close()
    unreal.log("Unreal Live Link Receiver stopped.")

def process_updates(delta_time):
    """Tick callback on the main thread to apply updates."""
    if _update_queue.empty():
        return
        
    # Drain the queue, keeping only the latest payload to avoid lag buildup
    latest_updates = None
    while not _update_queue.empty():
        latest_updates = _update_queue.get()
        
    if not latest_updates:
        return
        
    # Build a dictionary of current actors for fast lookup
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    actor_dict = {actor.get_actor_label(): actor for actor in actors}
    
    for obj_data in latest_updates:
        name = obj_data.get("name")
        if not name or name not in actor_dict:
            continue
            
        actor = actor_dict[name]
        
        # 1. Transform
        loc = obj_data.get("location")
        rot = obj_data.get("rotation")
        scl = obj_data.get("scale")
        
        if loc and rot and scl:
            # Blender +X, +Y, +Z (Z up) -> Unreal +X, -Y, +Z (Z up) (Approximate for 1:1 cm sync)
            # Actually, Blender is Z-up, Unreal is Z-up, but Y is flipped.
            # Scale in Blender is 1 unit = 1m. Unreal is 1 unit = 1cm. So multiply loc by 100.
            ue_loc = unreal.Vector(loc[0] * 100.0, loc[1] * -100.0, loc[2] * 100.0)
            
            # Rotations: Blender Euler (radians) -> Unreal Rotator (degrees)
            import math
            ue_rot = unreal.Rotator(
                pitch=math.degrees(rot[1]),  # Y -> Pitch
                yaw=math.degrees(rot[2]) * -1.0, # Z -> Yaw (inverted for left-handed)
                roll=math.degrees(rot[0])   # X -> Roll
            )
            
            ue_scl = unreal.Vector(scl[0], scl[1], scl[2])
            
            actor.set_actor_location_and_rotation(ue_loc, ue_rot, False, False)
            actor.set_actor_scale3d(ue_scl)
            
        # 2. Camera Properties
        if obj_data.get("type") == "CAMERA" and isinstance(actor, unreal.CameraActor):
            fov = obj_data.get("fov")
            if fov is not None:
                cam_comp = actor.get_component_by_class(unreal.CameraComponent)
                if cam_comp:
                    cam_comp.set_editor_property("field_of_view", fov)
                    
        # 3. Light Properties
        elif obj_data.get("type") == "LIGHT" and isinstance(actor, unreal.Light):
            energy = obj_data.get("energy")
            color = obj_data.get("color")
            
            light_comp = actor.get_component_by_class(unreal.LightComponent)
            if light_comp:
                if energy is not None:
                    light_comp.set_editor_property("intensity", energy) # Might need scaling
                if color is not None:
                    light_comp.set_editor_property("light_color", unreal.Color(int(color[0]*255), int(color[1]*255), int(color[2]*255), 255))

def start_livelink():
    global _receiver_thread, _stop_event, _tick_handle
    
    if _receiver_thread and _receiver_thread.is_alive():
        unreal.log_warning("Live Link is already running.")
        return
        
    _stop_event.clear()
    _receiver_thread = threading.Thread(target=udp_listener)
    _receiver_thread.daemon = True
    _receiver_thread.start()
    
    _tick_handle = unreal.register_slate_post_tick_callback(process_updates)

def stop_livelink():
    global _receiver_thread, _stop_event, _tick_handle
    
    _stop_event.set()
    if _receiver_thread:
        _receiver_thread.join(timeout=2.0)
        
    if _tick_handle:
        unreal.unregister_slate_post_tick_callback(_tick_handle)
        _tick_handle = None
