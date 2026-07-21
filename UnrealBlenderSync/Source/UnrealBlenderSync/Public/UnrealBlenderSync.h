#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class UNREALBLENDERSYNC_API FUnrealBlenderSyncModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
    static void TriggerSync(const FString& ExportType);
};
