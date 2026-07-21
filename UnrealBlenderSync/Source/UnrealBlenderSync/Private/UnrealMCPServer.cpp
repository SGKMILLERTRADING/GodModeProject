#include "UnrealMCPServer.h"
#include "Misc/Paths.h"
#include "HAL/PlatformFilemanager.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "JsonObjectConverter.h"
#include "JsonUtilities/Public/JsonObjectConverter.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "UObject/ConstructorHelpers.h"
#include "Engine/StaticMeshActor.h"
#include "Editor/UnrealEd/Public/Editor.h"
#include "Kismet/GameplayStatics.h"
#include "Runtime/Engine/Classes/Components/StaticMeshComponent.h"
#include "Interfaces/IPluginManager.h"
#include "UnrealBlenderSync.h"

FUnrealMCPServer::FUnrealMCPServer()
    : bRunning(false), ListenerSocket(nullptr), Thread(nullptr), Port(8000)
{
    LoadConfig();
}

FUnrealMCPServer::~FUnrealMCPServer()
{
    Stop();
}

void FUnrealMCPServer::LoadConfig()
{
    // Build the path to our plugin's own config file:
    // <PluginDir>/Config/UnrealMCPConfig.ini
    FString PluginConfigPath = FPaths::ConvertRelativePathToFull(
        FPaths::Combine(
            IPluginManager::Get().FindPlugin(TEXT("UnrealBlenderSync"))->GetBaseDir(),
            TEXT("Config"),
            TEXT("UnrealMCPConfig.ini")
        )
    );

    UE_LOG(LogTemp, Log, TEXT("[UnrealMCP] Loading config from: %s"), *PluginConfigPath);

    // Force-load the ini file into GConfig
    if (GConfig)
    {
        GConfig->LoadFile(PluginConfigPath);
        GConfig->GetInt(TEXT("MCP"), TEXT("Port"), Port, PluginConfigPath);
        GConfig->GetString(TEXT("MCP"), TEXT("AuthToken"), AuthToken, PluginConfigPath);
        GConfig->GetString(TEXT("MCP"), TEXT("SyncFolder"), SyncFolder, PluginConfigPath);
    }

    // Ensure defaults if missing
    if (Port <= 0)
    {
        Port = 8000;
    }
    if (AuthToken.IsEmpty())
    {
        AuthToken = TEXT("d9a7f3e8b6c04a92a5f2e1c4b9d7e3a1");
    }
    if (SyncFolder.IsEmpty())
    {
        SyncFolder = TEXT("C:/Users/sassy/OneDrive/Desktop/Unreal and Blender plugin and extension/SyncFolder");
    }

    UE_LOG(LogTemp, Log, TEXT("[UnrealMCP] Port=%d | Token=%s | Folder=%s"), Port, *AuthToken, *SyncFolder);
}

bool FUnrealMCPServer::Start()
{
    if (bRunning)
    {
        return true;
    }

    // Create socket
    ListenerSocket = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateSocket(NAME_Stream, TEXT("MCPListener"), false);
    if (!ListenerSocket)
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to create MCP listener socket"));
        return false;
    }
    // Bind
    FIPv4Address Addr;
    FIPv4Address::Parse(TEXT("127.0.0.1"), Addr);
    TSharedRef<FInternetAddr> InternetAddr = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
    InternetAddr->SetIp(Addr.Value);
    InternetAddr->SetPort(Port);
    bool bBound = ListenerSocket->Bind(*InternetAddr);
    if (!bBound)
    {
        UE_LOG(LogTemp, Error, TEXT("MCP server failed to bind to %s:%d"), *InternetAddr->ToString(false), Port);
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ListenerSocket);
        ListenerSocket = nullptr;
        return false;
    }
    ListenerSocket->Listen(8);
    bRunning = true;
    Thread = FRunnableThread::Create(this, TEXT("UnrealMCPServerThread"), 0, TPri_AboveNormal);
    UE_LOG(LogTemp, Log, TEXT("MCP server started on port %d"), Port);
    return true;
}

void FUnrealMCPServer::Stop()
{
    bRunning = false;
    if (ListenerSocket)
    {
        ListenerSocket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ListenerSocket);
        ListenerSocket = nullptr;
    }
    if (Thread)
    {
        Thread->Kill(true);
        delete Thread;
        Thread = nullptr;
    }
    UE_LOG(LogTemp, Log, TEXT("MCP server stopped"));
}

uint32 FUnrealMCPServer::Run()
{
    while (bRunning)
    {
        bool bHasPendingConnection = false;
        ListenerSocket->HasPendingConnection(bHasPendingConnection);
        if (bHasPendingConnection)
        {
            // Accept connection
            FSocket* ClientSocket = ListenerSocket->Accept(TEXT("MCPClient"));
            if (ClientSocket)
            {
                HandleClient(ClientSocket);
                ClientSocket->Close();
                ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ClientSocket);
            }
        }
        // Small sleep to avoid busy loop
        FPlatformProcess::Sleep(0.01f);
    }
    return 0;
}

void FUnrealMCPServer::Exit()
{
    Stop();
}

void FUnrealMCPServer::HandleClient(FSocket* ClientSocket)
{
    // Simple read loop (assume message fits in 4KB)
    const int32 BufferSize = 4096;
    TArray<uint8> ReceivedData;
    ReceivedData.SetNumZeroed(BufferSize);
    int32 BytesRead = 0;
    if (ClientSocket->Recv(ReceivedData.GetData(), BufferSize, BytesRead))
    {
        FString RequestJson = FString(ANSI_TO_TCHAR(reinterpret_cast<const char*>(ReceivedData.GetData()))).Left(BytesRead);
        ProcessRequest(RequestJson, ClientSocket);
    }
    else
    {
        UE_LOG(LogTemp, Warning, TEXT("MCP server failed to read data from client"));
    }
}

void FUnrealMCPServer::ProcessRequest(const FString& RequestJson, FSocket* ClientSocket)
{
    TSharedPtr<FJsonObject> RootObject;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RequestJson);
    if (!FJsonSerializer::Deserialize(Reader, RootObject) || !RootObject.IsValid())
    {
        SendResponse(ClientSocket, TEXT("{\"status\":\"error\",\"message\":\"Invalid JSON\"}"));
        return;
    }
    // Auth check
    FString ReceivedToken;
    if (!RootObject->TryGetStringField(TEXT("auth_token"), ReceivedToken) || ReceivedToken != AuthToken)
    {
        SendResponse(ClientSocket, TEXT("{\"status\":\"error\",\"message\":\"Invalid auth token\"}"));
        return;
    }
    FString Action;
    if (!RootObject->TryGetStringField(TEXT("action"), Action))
    {
        SendResponse(ClientSocket, TEXT("{\"status\":\"error\",\"message\":\"Missing action\"}"));
        return;
    }

    // Prepare response object
    TSharedPtr<FJsonObject> Resp = MakeShareable(new FJsonObject);
    Resp->SetStringField(TEXT("status"), TEXT("success"));

    // Simple dispatcher – only a subset is fully implemented for demo purposes
    if (Action == TEXT("get_asset_hierarchy"))
    {
        // For brevity, return placeholder list
        TArray<TSharedPtr<FJsonValue>> AssetsArray;
        // In a real implementation you would iterate over UPackage assets.
        Resp->SetArrayField(TEXT("assets"), AssetsArray);
    }
    else if (Action == TEXT("get_actor_hierarchy"))
    {
        TArray<TSharedPtr<FJsonValue>> ActorsArray;
        UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
        if (World)
        {
            for (TActorIterator<AActor> It(World); It; ++It)
            {
                AActor* Actor = *It;
                TSharedPtr<FJsonObject> ActorObj = MakeShareable(new FJsonObject);
                ActorObj->SetStringField(TEXT("name"), Actor->GetName());
                FVector Loc = Actor->GetActorLocation();
                ActorObj->SetNumberField(TEXT("x"), Loc.X);
                ActorObj->SetNumberField(TEXT("y"), Loc.Y);
                ActorObj->SetNumberField(TEXT("z"), Loc.Z);
                ActorsArray.Add(MakeShareable(new FJsonValueObject(ActorObj)));
            }
        }
        Resp->SetArrayField(TEXT("actors"), ActorsArray);
    }
    else if (Action == TEXT("create_actor"))
    {
        FString ClassName;
        FString NewName;
        RootObject->TryGetStringField(TEXT("class"), ClassName);
        RootObject->TryGetStringField(TEXT("name"), NewName);
        UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
        if (World && !ClassName.IsEmpty())
        {
            UClass* ActorClass = FindObject<UClass>(ANY_PACKAGE, *ClassName);
            if (ActorClass)
            {
                FActorSpawnParameters Params;
                Params.Name = *NewName;
                AActor* NewActor = World->SpawnActor<AActor>(ActorClass, FVector::ZeroVector, FRotator::ZeroRotator, Params);
                if (NewActor)
                {
                    Resp->SetStringField(TEXT("message"), FString::Printf(TEXT("Created %s"), *NewActor->GetName()));
                }
                else
                {
                    Resp->SetStringField(TEXT("status"), TEXT("error"));
                    Resp->SetStringField(TEXT("message"), TEXT("Failed to spawn actor"));
                }
            }
            else
            {
                Resp->SetStringField(TEXT("status"), TEXT("error"));
                Resp->SetStringField(TEXT("message"), TEXT("Class not found"));
            }
        }
    }
    else if (Action == TEXT("delete_actor"))
    {
        FString Name;
        RootObject->TryGetStringField(TEXT("name"), Name);
        UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
        if (World)
        {
            for (TActorIterator<AActor> It(World); It; ++It)
            {
                if (It->GetName() == Name)
                {
                    It->Destroy();
                    Resp->SetStringField(TEXT("message"), FString::Printf(TEXT("Deleted %s"), *Name));
                    break;
                }
            }
        }
    }
    else if (Action == TEXT("set_transform"))
    {
        FString Name;
        const TSharedPtr<FJsonObject>* TransformObj;
        if (RootObject->TryGetStringField(TEXT("name"), Name) && RootObject->TryGetObjectField(TEXT("transform"), TransformObj))
        {
            UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
            if (World)
            {
                for (TActorIterator<AActor> It(World); It; ++It)
                {
                    if (It->GetName() == Name)
                    {
                        float X = (*TransformObj)->GetNumberField(TEXT("x"));
                        float Y = (*TransformObj)->GetNumberField(TEXT("y"));
                        float Z = (*TransformObj)->GetNumberField(TEXT("z"));
                        It->SetActorLocation(FVector(X, Y, Z));
                        Resp->SetStringField(TEXT("message"), TEXT("Transform set"));
                        break;
                    }
                }
            }
        }
    }
    else if (Action == TEXT("trigger_sync"))
    {
        FString ExportType = TEXT("ALL");
        RootObject->TryGetStringField(TEXT("type"), ExportType);
        // Call existing module method – static helper
        FUnrealBlenderSyncModule::TriggerSync(ExportType);
        Resp->SetStringField(TEXT("message"), TEXT("Sync triggered"));
    }
    else if (Action == TEXT("get_metadata"))
    {
        FString MetaPath = SyncFolder / TEXT("UnrealMetadata.json");
        FString JsonStr;
        if (FFileHelper::LoadFileToString(JsonStr, *MetaPath))
        {
            TSharedPtr<FJsonObject> MetaObj;
            TSharedRef<TJsonReader<>> MetaReader = TJsonReaderFactory<>::Create(JsonStr);
            if (FJsonSerializer::Deserialize(MetaReader, MetaObj) && MetaObj.IsValid())
            {
                Resp->SetObjectField(TEXT("metadata"), MetaObj);
            }
        }
        else
        {
            Resp->SetObjectField(TEXT("metadata"), MakeShareable(new FJsonObject));
        }
    }
    else if (Action == TEXT("set_metadata"))
    {
        const TSharedPtr<FJsonObject>* MetaObj;
        if (RootObject->TryGetObjectField(TEXT("metadata"), MetaObj))
        {
            FString MetaPath = SyncFolder / TEXT("UnrealMetadata.json");
            FString OutStr;
            TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutStr);
            FJsonSerializer::Serialize((*MetaObj).ToSharedRef(), Writer);
            FFileHelper::SaveStringToFile(OutStr, *MetaPath);
            Resp->SetStringField(TEXT("message"), TEXT("Metadata saved"));
        }
    }
    else if (Action == TEXT("run_editor_command"))
    {
        FString Cmd;
        RootObject->TryGetStringField(TEXT("command"), Cmd);
        if (GEngine)
        {
            GEngine->Exec(nullptr, *Cmd);
            Resp->SetStringField(TEXT("message"), TEXT("Command executed"));
        }
    }
    else
    {
        Resp->SetStringField(TEXT("status"), TEXT("error"));
        Resp->SetStringField(TEXT("message"), TEXT("Unknown action"));
    }

    // Serialize response
    FString RespStr;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&RespStr);
    FJsonSerializer::Serialize(Resp.ToSharedRef(), Writer);
    SendResponse(ClientSocket, RespStr);
}

void FUnrealMCPServer::SendResponse(FSocket* ClientSocket, const FString& ResponseJson)
{
    FTCHARToUTF8 Converter(*ResponseJson);
    int32 BytesSent = 0;
    ClientSocket->Send((uint8*)Converter.Get(), Converter.Length(), BytesSent);
}
