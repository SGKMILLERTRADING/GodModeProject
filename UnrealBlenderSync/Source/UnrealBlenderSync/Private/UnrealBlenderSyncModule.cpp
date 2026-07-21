#include "UnrealBlenderSync.h"
#include "BlenderSyncExporter.h"
#include "Modules/ModuleManager.h"
#include "Interfaces/IPluginManager.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformFilemanager.h"
#include "JsonObjectConverter.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FeedbackContext.h"
#include "HAL/FileManager.h"
#include "Engine/Engine.h"
#include "UnrealMCPServer.h"
#include "Misc/MessageDialog.h"
#include "UObject/ConstructorHelpers.h"
#include "ConsoleManager.h"
#include "Containers/Ticker.h"

// Helper to write response.json
static void WriteResponse(const FString& ExportPath, bool bSuccess)
{
    const FString RespDir = FPaths::ProjectSavedDir() / TEXT("BlenderSync");
    IFileManager::Get().MakeDirectory(*RespDir, true);
    const FString RespPath = RespDir / TEXT("response.json");

    TSharedPtr<FJsonObject> Obj = MakeShareable(new FJsonObject);
    Obj->SetStringField(TEXT("status"), bSuccess ? TEXT("ok") : TEXT("error"));
    Obj->SetStringField(TEXT("filepath"), ExportPath);
    FString OutStr;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutStr);
    FJsonSerializer::Serialize(Obj.ToSharedRef(), Writer);
    FFileHelper::SaveStringToFile(OutStr, *RespPath);
}

static void ExportUAssetCommand(const TArray<FString>& Args)
{
    if (Args.Num() < 2)
    {
        UE_LOG(LogTemp, Error, TEXT("Usage: BlenderExportUAsset <AssetPath> <format>"));
        return;
    }
    const FString AssetPath = Args[0];
    const FString Format = Args[1].ToLower();

    // Resolve package name from a full path or asset reference
    FString PackageName;
    if (!FPackageName::TryConvertFilenameToLongPackageName(AssetPath, PackageName))
    {
        // Maybe it's already a long package name
        PackageName = AssetPath;
    }
    UObject* Asset = StaticLoadObject(UObject::StaticClass(), nullptr, *PackageName);
    if (!Asset)
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to load asset %s"), *PackageName);
        WriteResponse(TEXT(""), false);
        return;
    }

    const FString ExportDir = FPaths::ProjectSavedDir() / TEXT("BlenderSync");
    IFileManager::Get().MakeDirectory(*ExportDir, true);
    FString Ext = TEXT(".fbx");
    if (Format == TEXT("gltf") || Format == TEXT("glb"))
        Ext = TEXT(".glb");
    else if (Format == TEXT("usdz") || Format == TEXT("usd"))
        Ext = TEXT(".usdz");
    const FString ExportPath = ExportDir / TEXT("export") + Ext;

    bool bSuccess = false;
    if (Format == TEXT("fbx"))
    {
        bSuccess = FBlenderSyncExporter::ExportAssetToFBX(Asset, ExportPath);
    }
    else // For simplicity, reuse FBX exporter for other formats (you can replace with GLTF/USDC later)
    {
        bSuccess = FBlenderSyncExporter::ExportAssetToFBX(Asset, ExportPath);
    }

    WriteResponse(ExportPath, bSuccess);
    if (bSuccess)
        UE_LOG(LogTemp, Log, TEXT("Exported %s to %s"), *PackageName, *ExportPath);
    else
        UE_LOG(LogTemp, Error, TEXT("Export failed for %s"), *PackageName);
}

// Static server instance
static FUnrealMCPServer* GUnrealMCPServer = nullptr;

void FUnrealBlenderSyncModule::StartupModule()
{
    // Start MCP server
    GUnrealMCPServer = new FUnrealMCPServer();
    if (!GUnrealMCPServer->Start())
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to start Unreal MCP server"));
    }
    else
    {
        UE_LOG(LogTemp, Log, TEXT("Unreal MCP server started on port %d"), 8000);
    }
    // Register console command as before
    IConsoleManager::Get().RegisterConsoleCommand(
        TEXT("BlenderExportUAsset"),
        TEXT("Export a .uasset to a format for Blender"),
        FConsoleCommandWithArgsDelegate::CreateStatic(&ExportUAssetCommand),
        ECVF_Default);
}

void FUnrealBlenderSyncModule::ShutdownModule()
{
    // Stop MCP server
    if (GUnrealMCPServer)
    {
        GUnrealMCPServer->Stop();
        delete GUnrealMCPServer;
        GUnrealMCPServer = nullptr;
    }
    // Console command is automatically unregistered on module unload.
}

// Static method exposed to MCP server
void FUnrealBlenderSyncModule::TriggerSync(const FString& ExportType)
{
    UE_LOG(LogTemp, Log, TEXT("TriggerSync called with ExportType=%s"), *ExportType);
}



IMPLEMENT_MODULE(FUnrealBlenderSyncModule, UnrealBlenderSync)
