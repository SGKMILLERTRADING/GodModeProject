import sys
sys.path.insert(0, r'C:\Users\sassy\OneDrive\Desktop\Unreal and Blender plugin and extension')
from blender_addon.mcp_server import mcp
tools = mcp.list_tools()
print(f"BLENDER MCP: {len(tools)} tools loaded")
for t in tools:
    print(f"  - {t.name}: {t.description[:60]}")
