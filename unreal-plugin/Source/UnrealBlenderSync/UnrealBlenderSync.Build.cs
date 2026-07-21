using UnrealBuildTool;
using System.Collections.Generic;

public class UnrealBlenderSync : ModuleRules
{
    public UnrealBlenderSync(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(
            new string[] {
                "Core",
                "CoreUObject",
                "Engine"
            }
        );

        PrivateDependencyModuleNames.AddRange(
            new string[] {
                "InputCore",
                "Slate",
                "SlateCore",
                "EditorStyle",
                "UnrealEd",
                "LevelEditor",
                "ToolMenus",
                "DirectoryWatcher",
                "AssetTools",
                "FbxExporter",
                "Json",
                "JsonUtilities",
                "Sockets",
                "Networking",
                "Projects"
            }
        );

        DynamicallyLoadedModuleNames.AddRange(
            new string[] {
            }
        );
    }
}
