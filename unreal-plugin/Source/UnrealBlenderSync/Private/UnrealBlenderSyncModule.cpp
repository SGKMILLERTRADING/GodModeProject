#include "UnrealBlenderSync.h"
#include "LevelEditor.h"
#include "ToolMenus.h"
#include "EditorStyleSet.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "UnrealExporter.h"

#define LOCTEXT_NAMESPACE "FUnrealBlenderSyncModule"

#include "IDirectoryWatcher.h"
#include "DirectoryWatcherModule.h"
#include "AssetToolsModule.h"
#include "IAssetTools.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Interfaces/IPv4/IPv4Address.h"
#include "HAL/PlatformProcess.h"
#include "Interfaces/IPluginManager.h"
#include "Misc/Paths.h"

void FUnrealBlenderSyncModule::StartupModule()
{
    FToolMenuOwnerScoped OwnerScoped(this);
    RegisterMenus();
    RegisterDirectoryWatcher();

    // Check if TCP connection to port 8001 on localhost works
    ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
    bool bIsServerRunning = false;
    if (SocketSubsystem)
    {
        TSharedRef<FInternetAddr> Addr = SocketSubsystem->CreateInternetAddr();
        bool bIsValid = false;
        Addr->SetIp(TEXT("127.0.0.1"), bIsValid);
        Addr->SetPort(8001);

        FSocket* Socket = SocketSubsystem->CreateSocket(NAME_Stream, TEXT("PingSocket"), false);
        if (Socket)
        {
            if (Socket->Connect(*Addr))
            {
                bIsServerRunning = true;
            }
            Socket->Close();
            SocketSubsystem->DestroySocket(Socket);
        }
    }

    if (!bIsServerRunning)
    {
        FString PythonExe = TEXT("C:\\Python314\\python.exe");
        FString ScriptPath = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../unreal_socket_server.py"));
        
        if (!FPaths::FileExists(ScriptPath))
        {
            if (IPluginManager::Get().FindPlugin(TEXT("UnrealBlenderSync")).IsValid())
            {
                ScriptPath = IPluginManager::Get().FindPlugin(TEXT("UnrealBlenderSync"))->GetBaseDir() / TEXT("../../unreal_socket_server.py");
                ScriptPath = FPaths::ConvertRelativePathToFull(ScriptPath);
            }
        }

        // Default path if not found (just passed to python, it might fail if not exists)
        if (!FPaths::FileExists(ScriptPath))
        {
            ScriptPath = TEXT("unreal_socket_server.py");
        }

        FString Args = FString::Printf(TEXT("\"%s\""), *ScriptPath);
        uint32 ProcessID = 0;
        FPlatformProcess::CreateProc(*PythonExe, *Args, true, false, false, &ProcessID, 0, nullptr, nullptr, nullptr);
        UE_LOG(LogTemp, Log, TEXT("Auto-launched unreal_socket_server.py with ProcessID: %d"), ProcessID);
    }
}

void FUnrealBlenderSyncModule::ShutdownModule()
{
    if (UToolMenus::IsToolMenusEnabled())
    {
        UToolMenus::UnregisterOwner(this);
    }

    // Unregister directory watcher
    FDirectoryWatcherModule* DirectoryWatcherModule = FModuleManager::GetModulePtr<FDirectoryWatcherModule>(TEXT("DirectoryWatcher"));
    if (DirectoryWatcherModule)
    {
        FString WatchDir = FPaths::ProjectSavedDir() / TEXT("BlenderSync");
        DirectoryWatcherModule->Get()->UnregisterDirectoryChangedCallback_Handle(WatchDir, DirectoryWatcherHandle);
    }
}

void FUnrealBlenderSyncModule::RegisterDirectoryWatcher()
{
    FDirectoryWatcherModule& DirectoryWatcherModule = FModuleManager::LoadModuleChecked<FDirectoryWatcherModule>(TEXT("DirectoryWatcher"));
    IDirectoryWatcher* DirectoryWatcher = DirectoryWatcherModule.Get();

    if (DirectoryWatcher)
    {
        FString WatchDir = FPaths::ProjectSavedDir() / TEXT("BlenderSync");
        if (!FPlatformFileManager::Get().GetPlatformFile().DirectoryExists(*WatchDir))
        {
            FPlatformFileManager::Get().GetPlatformFile().CreateDirectoryTree(*WatchDir);
        }

        DirectoryWatcher->RegisterDirectoryChangedCallback_Handle(
            WatchDir,
            IDirectoryWatcher::FDirectoryChanged::CreateRaw(this, &FUnrealBlenderSyncModule::OnDirectoryChanged),
            DirectoryWatcherHandle,
            IDirectoryWatcher::WatchOptions::IncludeDirectoryChanges
        );
    }
}

void FUnrealBlenderSyncModule::OnDirectoryChanged(const TArray<FFileChangeData>& FileChanges)
{
    for (const FFileChangeData& Change : FileChanges)
    {
        if (Change.Action == FFileChangeData::FCA_Added || Change.Action == FFileChangeData::FCA_Modified)
        {
            if (Change.Filename.EndsWith(TEXT("request.json")))
            {
                FString JsonContent;
                if (FFileHelper::LoadFileToString(JsonContent, *Change.Filename))
                {
                    TSharedPtr<FJsonObject> JsonObject;
                    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
                    if (FJsonSerializer::Deserialize(Reader, JsonObject) && JsonObject.IsValid())
                    {
                        FString Action = JsonObject->GetStringField(TEXT("action"));
                        if (Action == TEXT("export_uasset"))
                        {
                            FString UAssetPath = JsonObject->GetStringField(TEXT("filepath"));
                            FString Format = JsonObject->GetStringField(TEXT("format"));
                            
                            FString Ext = (Format == TEXT("GLTF")) ? TEXT(".glb") : (Format == TEXT("USDZ") ? TEXT(".usdc") : TEXT(".fbx"));
                            FString ExportDest = FPaths::ProjectSavedDir() / TEXT("BlenderSync") / (TEXT("temp_export") + Ext);
                            
                            // Convert Absolute Path to Package Name
                            FString PackageName;
                            bool bSuccess = false;
                            
                            if (FPackageName::TryConvertFilenameToLongPackageName(UAssetPath, PackageName))
                            {
                                // Load the Object
                                UObject* Asset = StaticLoadObject(UObject::StaticClass(), nullptr, *PackageName);
                                if (Asset)
                                {
                                    bSuccess = FUnrealExporter::ExportAssetToFBX(Asset, ExportDest);
                                }
                                else
                                {
                                    UE_LOG(LogTemp, Error, TEXT("Failed to load asset at package path: %s"), *PackageName);
                                }
                            }
                            else
                            {
                                UE_LOG(LogTemp, Error, TEXT("Could not convert %s to package name"), *UAssetPath);
                            }
                            
                            // Write response.json
                            TSharedPtr<FJsonObject> ResponseObj = MakeShareable(new FJsonObject);
                            ResponseObj->SetStringField(TEXT("status"), bSuccess ? TEXT("success") : TEXT("error"));
                            ResponseObj->SetStringField(TEXT("filepath"), ExportDest);
                            
                            FString ResponseContent;
                            TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&ResponseContent);
                            FJsonSerializer::Serialize(ResponseObj.ToSharedRef(), Writer);
                            
                            FString ResponseFile = FPaths::ProjectSavedDir() / TEXT("BlenderSync") / TEXT("response.json");
                            FFileHelper::SaveStringToFile(ResponseContent, *ResponseFile);
                            
                            UE_LOG(LogTemp, Log, TEXT("Processed uasset export request for %s"), *UAssetPath);
                        }
                    }
                }
            }
            else if (Change.Filename.EndsWith(TEXT(".fbx")) && !Change.Filename.Contains(TEXT("temp_export")))
            {
                UE_LOG(LogTemp, Log, TEXT("Auto-importing new FBX from Blender: %s"), *Change.Filename);
                IAssetTools& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();
                
                TArray<FString> FilesToImport;
                FilesToImport.Add(Change.Filename);
                
                FString DestinationPath = TEXT("/Game/BlenderSync");
                AssetTools.ImportAssets(FilesToImport, DestinationPath);
            }
        }
    }
}


void FUnrealBlenderSyncModule::RegisterMenus()
{
    UToolMenus::RegisterStartupCallback(FSimpleMulticastDelegate::FDelegate::CreateLambda([this]() {
        UToolMenu* Menu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Tools");
        FToolMenuSection& Section = Menu->FindOrAddSection("LevelEditor");
        Section.AddMenuEntry(
            "UnrealBlenderSyncExport",
            LOCTEXT("UnrealBlenderSyncExport", "Export Selected to Blender"),
            LOCTEXT("UnrealBlenderSyncExportTooltip", "Export selected assets, skin weights, hair, and animation to Blender."),
            FSlateIcon(FEditorStyle::GetStyleSetName(), "MainFrame.MainMenu.File"),
            FUIAction(FExecuteAction::CreateRaw(this, &FUnrealBlenderSyncModule::ExportSelectedToBlender))
        );
    }));
}

void FUnrealBlenderSyncModule::ExportSelectedToBlender()
{
    FString DefaultExportPath = FPaths::ProjectSavedDir() / TEXT("BlenderSync") / TEXT("export.fbx");
    if (FUnrealExporter::ExportSelectedToFBX(DefaultExportPath, true, true, true, true))
    {
        UE_LOG(LogTemp, Log, TEXT("Exported selected assets to %s"), *DefaultExportPath);
    }
    else
    {
        UE_LOG(LogTemp, Error, TEXT("UnrealBlenderSync export failed."));
    }
}

#undef LOCTEXT_NAMESPACE
