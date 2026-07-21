#pragma once

#include "CoreMinimal.h"

class FUnrealExporter
{
public:
    /**
    /** Exports the specified Asset to an FBX file. */
    static bool ExportAssetToFBX(UObject* Asset, const FString& ExportPath);

    /** Exports the currently selected objects to an FBX file. */
    static bool ExportSelectedToFBX(const FString& ExportPath, bool bMesh = true, bool bAnimation = true, bool bMaterials = true, bool bTextures = true);
};
