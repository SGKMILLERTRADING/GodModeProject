import os
import json

def get_metadata_path(sync_dir):
    """Return the full path to the metadata JSON file inside the sync directory."""
    return os.path.join(sync_dir, "metadata.json")

def load_metadata(sync_dir):
    """Load metadata dictionary from the sync folder.
    Returns an empty dict if the file does not exist or is invalid.
    """
    path = get_metadata_path(sync_dir)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_metadata(sync_dir, data):
    """Write the metadata dictionary to the sync folder.
    ``data`` should be a JSON‑serializable dict.
    """
    path = get_metadata_path(sync_dir)
    os.makedirs(sync_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
