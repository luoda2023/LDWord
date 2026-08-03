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
; {autopf} resolves to LocalAppData\Programs for the default per-user mode,
; and to Program Files only when the user explicitly selects admin mode.
DefaultDirName={autopf}\Alavette Form
DefaultGroupName=Alavette Form
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
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
Name: "english"; MessagesFile: "compiler:Default.isl"

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
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："; Flags: checkedonce

[Run]
Filename: "{app}\app\{#AppExeName}"; Description: "启动 Alavette Form"; WorkingDir: "{app}\app"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; User settings, logs, provider credentials, and working documents live under
; %LOCALAPPDATA%\Alavette-Form and are deliberately preserved.
Type: dirifempty; Name: "{app}\app"
Type: dirifempty; Name: "{app}"
