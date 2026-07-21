#pragma once

#include "CoreMinimal.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "Misc/ConfigCacheIni.h"

/**
 * Simple TCP server that listens for JSON‑RPC style requests from an MCP client.
 * Reads configuration from UnrealMCPConfig.ini (Port, AuthToken, SyncFolder).
 * Each request must contain an "auth_token" field matching the configured token.
 * Supported actions are defined in UnrealMCPServer.cpp.
 */
class FUnrealMCPServer : public FRunnable
{
public:
    FUnrealMCPServer();
    virtual ~FUnrealMCPServer();

    // Starts listening on the configured port.
    bool Start();
    // Stops the server and cleans up.
    void Stop();

    // FRunnable interface
    virtual uint32 Run() override;
    virtual void Exit() override;

private:
    bool bRunning = false;
    FSocket* ListenerSocket = nullptr;
    FRunnableThread* Thread = nullptr;
    int32 Port = 8000;
    FString AuthToken;
    FString SyncFolder;

    void LoadConfig();
    void HandleClient(FSocket* ClientSocket);
    void ProcessRequest(const FString& RequestJson, FSocket* ClientSocket);
    void SendResponse(FSocket* ClientSocket, const FString& ResponseJson);
};
