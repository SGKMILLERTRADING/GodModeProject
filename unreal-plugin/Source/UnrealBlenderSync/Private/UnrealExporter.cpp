#include "UnrealExporter.h"
#include "Misc/Paths.h"
#include "HAL/PlatformFileManager.h"
#include "AssetExportTask.h"
#include "Exporters/Exporter.h"
#include "UObject/UObjectGlobals.h"

bool FUnrealExporter::ExportAssetToFBX(UObject* Asset, const FString& ExportPath)
{
    if (!Asset) return false;

    FString Directory = FPaths::GetPath(ExportPath);
    if (!FPlatformFileManager::Get().GetPlatformFile().DirectoryExists(*Directory))
    {
        FPlatformFileManager::Get().GetPlatformFile().CreateDirectoryTree(*Directory);
    }

    UAssetExportTask* ExportTask = NewObject<UAssetExportTask>();
    ExportTask->Object = Asset;
    ExportTask->Filename = ExportPath;
    ExportTask->bAutomated = true;
    ExportTask->bPrompt = false;
    ExportTask->Options = nullptr; 

    return UExporter::RunAssetExportTask(ExportTask);
}

bool FUnrealExporter::ExportSelectedToFBX(const FString& ExportPath, bool bMesh, bool bAnimation, bool bMaterials, bool bTextures)
{
    // ...
    return true;
}

