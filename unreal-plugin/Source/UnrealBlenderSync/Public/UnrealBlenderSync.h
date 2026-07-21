#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FUnrealBlenderSyncModule : public IModuleInterface
{
public:
    static inline FUnrealBlenderSyncModule& Get()
    {
        return FModuleManager::LoadModuleChecked<FUnrealBlenderSyncModule>("UnrealBlenderSync");
    }

    static inline bool IsAvailable()
    {
        return FModuleManager::Get().IsModuleLoaded("UnrealBlenderSync");
    }

    virtual void StartupModule() override;
    virtual void ShutdownModule() override;

private:
    void RegisterMenus();
    void ExportSelectedToBlender();

    // Directory watcher for automatic FBX import
    void RegisterDirectoryWatcher();
    void OnDirectoryChanged(const TArray<struct FFileChangeData>& FileChanges);

    FDelegateHandle DirectoryWatcherHandle;
};
