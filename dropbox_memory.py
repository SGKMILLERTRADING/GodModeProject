import json
import os
from datetime import datetime

def check_project_plans(project_name: str, dropbox_path: str) -> dict:
    file_path = os.path.join(dropbox_path, "AI_Plans", project_name, "plans.json")
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}

def register_active_task(project_name: str, dropbox_path: str, task_id: str, author: str, engine: str, task_description: str, location: str) -> dict:
    file_path = os.path.join(dropbox_path, "AI_Plans", project_name, "plans.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    data = {"tasks": []}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                data = json.load(f)
        except:
            pass
    
    task = {
        "task_id": task_id,
        "status": "IN_PROGRESS",
        "author": author,
        "engine": engine,
        "task_description": task_description,
        "location": location,
        "start_time": datetime.now().isoformat()
    }
    if "tasks" not in data:
        data["tasks"] = []
    data["tasks"].append(task)
    
    with open(file_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return {"status": "success", "task": task}

def complete_active_task(project_name: str, dropbox_path: str, task_id: str, status: str, notes: str, assets: list) -> dict:
    file_path = os.path.join(dropbox_path, "AI_Plans", project_name, "plans.json")
    if not os.path.exists(file_path):
        return {"error": "plans.json not found"}
    
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return {"error": str(e)}
    
    found = False
    for task in data.get("tasks", []):
        if task.get("task_id") == task_id:
            task["status"] = status
            task["notes"] = notes
            task["assets"] = assets
            task["end_time"] = datetime.now().isoformat()
            found = True
            break
    
    if not found:
        return {"error": "Task not found"}
        
    with open(file_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return {"status": "success", "message": f"Task {task_id} completed."}

def initialize_project_brain(project_name: str, dropbox_path: str) -> dict:
    """Lead AI initializes the folder structure and generates a Universal Prompt."""
    if not dropbox_path or not os.path.exists(dropbox_path):
        return {"status": "error", "message": "Dropbox path is invalid or empty. User must set this in Blender Preferences first."}
        
    plans_dir = os.path.join(dropbox_path, "AI_Plans", project_name)
    research_dir = os.path.join(plans_dir, "Research")
    
    os.makedirs(plans_dir, exist_ok=True)
    os.makedirs(research_dir, exist_ok=True)
    
    universal_prompt = f"""[GOD MODE UNIVERSAL CONNECTION PROMPT]
Project Name: {project_name}
Dropbox Memory Location: {plans_dir}

ATTENTION ALL AI ASSISTANTS:
Before you begin ANY task on this project, you MUST:
1. Check '{plans_dir}/plans.json' to ensure your task is not already IN_PROGRESS or DONE.
2. Check the '{research_dir}' folder for any relevant .md research notes.
3. If a research note contains '❌ [BAD CODE]', DO NOT use the logic inside it.
4. If a research note contains '✅ [GOOD CODE]', you are encouraged to use its logic.
5. Record your findings in '{research_dir}' to help the hive mind.
6. When starting your task, use 'register_active_task', and when finishing, use 'complete_active_task'.
"""
    # Write a quick README in the research folder
    readme_path = os.path.join(research_dir, "README.md")
    if not os.path.exists(readme_path):
        with open(readme_path, "w", encoding='utf-8') as f:
            f.write("# God Mode Research Folder\nAll AI notes and validated code snippets go here.")
            
    return {"status": "success", "universal_prompt": universal_prompt, "research_path": research_dir}

def add_research_note(project_name: str, dropbox_path: str, topic: str, content: str) -> dict:
    """Creates or overwrites a Markdown research note."""
    research_dir = os.path.join(dropbox_path, "AI_Plans", project_name, "Research")
    os.makedirs(research_dir, exist_ok=True)
    
    # Sanitize topic string
    safe_topic = "".join(x for x in topic if x.isalnum() or x in " _-").strip()
    file_path = os.path.join(research_dir, f"{safe_topic}.md")
    
    with open(file_path, "w", encoding='utf-8') as f:
        f.write(content)
        
    return {"status": "success", "message": f"Research note saved to {file_path}"}

def read_research_notes(project_name: str, dropbox_path: str) -> dict:
    """Lists all research notes and returns their content and validation status."""
    research_dir = os.path.join(dropbox_path, "AI_Plans", project_name, "Research")
    if not os.path.exists(research_dir):
        return {"status": "error", "message": f"Research directory not found: {research_dir}"}
        
    notes = {}
    for filename in os.listdir(research_dir):
        if filename.endswith(".md"):
            with open(os.path.join(research_dir, filename), "r", encoding='utf-8') as f:
                content = f.read()
                
            status = "PENDING"
            if "✅ [GOOD CODE]" in content:
                status = "GOOD"
            elif "❌ [BAD CODE]" in content:
                status = "BAD"
                
            notes[filename] = {
                "status": status,
                "content": content
            }
            
    return {"status": "success", "notes": notes}

def validate_code_snippet(project_name: str, dropbox_path: str, topic: str, is_good: bool, notes: str) -> dict:
    """Appends a validation header to an existing research note."""
    research_dir = os.path.join(dropbox_path, "AI_Plans", project_name, "Research")
    safe_topic = "".join(x for x in topic if x.isalnum() or x in " _-").strip()
    file_path = os.path.join(research_dir, f"{safe_topic}.md")
    
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"Research note '{topic}' not found."}
        
    with open(file_path, "r", encoding='utf-8') as f:
        content = f.read()
        
    # Remove existing tags to avoid duplicates
    content = content.replace("✅ [GOOD CODE]\n", "")
    content = content.replace("❌ [BAD CODE]\n", "")
    
    tag = "✅ [GOOD CODE]\n" if is_good else "❌ [BAD CODE]\n"
    validation_note = f"\n\n--- \n**Validation Notes ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}):**\n{notes}\n"
    
    new_content = tag + content + validation_note
    
    with open(file_path, "w", encoding='utf-8') as f:
        f.write(new_content)
        
    return {"status": "success", "message": f"Validated '{topic}' as {'GOOD' if is_good else 'BAD'}."}
