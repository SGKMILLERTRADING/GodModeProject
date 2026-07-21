using UnrealBuildTool;

public class UnrealBlenderSync : ModuleRules
{
    public UnrealBlenderSync(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PrivatePCHHeaderFile = "Public/UnrealBlenderSync.h";

        PublicDependencyModuleNames.AddRange(new string[] {
            "Core",
            "CoreUObject",
            "GLTFExporter",
            "Engine",
            "UnrealEd",
            "EditorStyle",
            "AssetTools",
            "Json",
            "JsonUtilities"
        });

        PrivateDependencyModuleNames.AddRange(new string[] {
            "Projects"
        });
    }
}
