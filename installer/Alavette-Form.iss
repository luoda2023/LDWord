; Alavette Form V1 installer. Values that vary per build are supplied with /D.

#ifndef AppVersion
  #error AppVersion must be supplied by the release pipeline
#endif
#ifndef SourceDir
  #error SourceDir must be supplied by the release pipeline
#endif
#ifndef OutputDir
  #error OutputDir must be supplied by the release pipeline
#endif
#ifndef OutputBaseFilename
  #error OutputBaseFilename must be supplied by the release pipeline
#endif

#define AppName "Alavette Form"
#define AppPublisher "Alavette"
#define AppExeName "Alavette-Form.exe"
#define AppIdValue "{5C548E6B-72CF-4A77-B8E4-7D2A94B777D4}"

[Setup]
AppId={{5C548E6B-72CF-4A77-B8E4-7D2A94B777D4}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
; V1 is deliberately current-user only: no UAC prompt and one deterministic
; writable installation location for every supported setup path.
DefaultDirName={localappdata}\Programs\Alavette Form
DefaultGroupName=Alavette Form
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
SetupIconFile=assets\Alavette-Form-Setup.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UsePreviousAppDir=yes
UsePreviousTasks=yes
DisableProgramGroupPage=yes
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=no
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\app\{#AppExeName}
SetupLogging=yes
#ifdef SignedBuild
SignTool=release
SignedUninstaller=yes
#endif

[Languages]
; Keep the Chinese messages in the repository so release output does not
; depend on optional language files installed on the build machine.
Name: "chinesesimplified"; MessagesFile: "languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimplified.DowngradeBlocked=已安装的版本 %1 高于此安装包版本 %2。为避免配置或文件不兼容，安装程序已阻止降级。请改用相同或更新版本。
english.DowngradeBlocked=Installed version %1 is newer than this setup package (%2). Setup blocked the downgrade to prevent incompatible files or settings. Use the same or a newer version.
chinesesimplified.LegacyMigrationFailed=安装程序无法把旧版用户方案迁移到新的用户数据目录。为避免数据丢失，安装已停止，原版本保持不变。请检查磁盘空间和目录权限后重试。
english.LegacyMigrationFailed=Setup could not migrate legacy user presets to the new user-data directory. Installation stopped before replacing the existing version. Check free space and folder permissions, then try again.
chinesesimplified.UninstallDataPrompt=是否同时删除当前用户的 Alavette Form 设置、方案、日志和已保存的 API 凭据？%n%n选择“否”可在以后重新安装时继续使用这些数据。
english.UninstallDataPrompt=Also remove the current user's Alavette Form settings, presets, logs, and saved API credentials?%n%nChoose No to keep this data for a future reinstall.

[InstallDelete]
; The payload is wholly application-owned. Replacing it prevents stale
; PyInstaller files from surviving a 1.0.x in-place upgrade.
Type: filesandordirs; Name: "{app}\app"

[Dirs]
Name: "{app}\app"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Alavette Form"; Filename: "{app}\app\{#AppExeName}"; WorkingDir: "{app}\app"
Name: "{autodesktop}\Alavette Form"; Filename: "{app}\app\{#AppExeName}"; WorkingDir: "{app}\app"; Tasks: desktopicon

[Tasks]
; Checked for a fresh install; checkedonce avoids restoring a shortcut that a
; user deliberately removed before an in-place upgrade.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Run]
Filename: "{app}\app\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; WorkingDir: "{app}\app"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\app\{#AppExeName}"; Parameters: "--internal-uninstall-clean-user-data"; Flags: runhidden skipifdoesntexist; Check: ShouldDeleteUserData; RunOnceId: "ClearCurrentUserData"

[UninstallDelete]
; Current-user data is preserved unless the user explicitly opts into cleanup.
Type: dirifempty; Name: "{app}\app"
Type: dirifempty; Name: "{app}"

[Code]
var
  DeleteUserData: Boolean;

function MigrateLegacyDirectory(const SourceDir, DestinationDir: String): Boolean;
var
  FindRec: TFindRec;
  SourcePath: String;
  DestinationPath: String;
begin
  Result := True;
  if not DirExists(SourceDir) then
    Exit;
  if not ForceDirectories(DestinationDir) then
  begin
    Result := False;
    Exit;
  end;
  if FindFirst(AddBackslash(SourceDir) + '*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          SourcePath := AddBackslash(SourceDir) + FindRec.Name;
          DestinationPath := AddBackslash(DestinationDir) + FindRec.Name;
          if (FindRec.Attributes and FILE_ATTRIBUTE_REPARSE_POINT) = 0 then
          begin
            if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            begin
              if not MigrateLegacyDirectory(SourcePath, DestinationPath) then
                Result := False;
            end
            else if not FileExists(DestinationPath) then
            begin
              if not CopyFile(SourcePath, DestinationPath, True) then
                Result := False;
            end;
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function MigrateLegacyUserDataFromRoot(
  const LegacyRoot, UserRoot: String
): Boolean;
begin
  Result := True;
  if not MigrateLegacyDirectory(LegacyRoot + '\header_footer_presets',
    UserRoot + '\header_footer_presets') then
    Result := False;
  if not MigrateLegacyDirectory(LegacyRoot + '\heading_numbering_schemes',
    UserRoot + '\heading_numbering_schemes') then
    Result := False;
  if not MigrateLegacyDirectory(
    LegacyRoot + '\config_library\masters\official\user',
    UserRoot + '\config_library\masters\official\user') then
    Result := False;
  if not MigrateLegacyDirectory(LegacyRoot + '\config_library\masters\exam\user',
    UserRoot + '\config_library\masters\exam\user') then
    Result := False;
end;

function MigrateLegacyUserData: Boolean;
var
  LegacyRoot: String;
  UserRoot: String;
begin
  Result := True;
  LegacyRoot := ExpandConstant('{app}\app');
  UserRoot := ExpandConstant('{localappdata}\Alavette-Form');
  if not MigrateLegacyUserDataFromRoot(LegacyRoot, UserRoot) then
    Result := False;
  if not MigrateLegacyUserDataFromRoot(LegacyRoot + '\_internal', UserRoot) then
    Result := False;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  InstalledVersion: Int64;
  PackageVersion: Int64;
begin
  Result := '';
  if GetPackedVersion(
       ExpandConstant('{app}\app\{#AppExeName}'), InstalledVersion
     ) and StrToVersion('{#AppVersion}.0', PackageVersion)
       and (ComparePackedVersion(InstalledVersion, PackageVersion) > 0) then
  begin
    Result := FmtMessage(CustomMessage('DowngradeBlocked'), [VersionToStr(InstalledVersion), '{#AppVersion}']);
    Exit;
  end;
  if not MigrateLegacyUserData then
    Result := CustomMessage('LegacyMigrationFailed');
end;

function InitializeUninstall: Boolean;
begin
  DeleteUserData := False;
  if not UninstallSilent then
  begin
    DeleteUserData := MsgBox(
      CustomMessage('UninstallDataPrompt'),
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    ) = IDYES;
  end;
  Result := True;
end;

function ShouldDeleteUserData: Boolean;
begin
  Result := DeleteUserData;
end;
