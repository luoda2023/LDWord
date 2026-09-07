; LDWord 安装程序 (NSIS 3)
Unicode True
!include "MUI2.nsh"

Name "LDWord"
OutFile "LDWord_Setup.exe"
InstallDir "$PROGRAMFILES64\LDWord"
InstallDirRegKey HKLM "Software\LDWord" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
CRCCheck on

VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "LDWord"
VIAddVersionKey "CompanyName" "LUODA"
VIAddVersionKey "FileDescription" "LDWord 工程文档智能排版与AI写作"
VIAddVersionKey "ProductVersion" "1.0.0"
VIAddVersionKey "LegalCopyright" "Copyright (C) LUODA"

!define MUI_ABORTWARNING
!define MUI_ICON "app_icon.ico"
!define MUI_UNICON "app_icon.ico"
!define MUI_WELCOMEPAGE_TITLE "欢迎安装 LDWord"
!define MUI_WELCOMEPAGE_TEXT "本向导将引导您安装 LDWord 工程文档智能排版与 AI 写作软件。`n`n点击“下一步”继续。"
!define MUI_FINISHPAGE_RUN "$INSTDIR\LDWord.exe"
!define MUI_FINISHPAGE_RUN_TEXT "立即运行 LDWord"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

Section "LDWord" SecMain
  SetOutPath "$INSTDIR"
  File /r "dist\LDWord\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\LDWord"
  CreateShortCut "$SMPROGRAMS\LDWord\LDWord.lnk" "$INSTDIR\LDWord.exe"
  CreateShortCut "$SMPROGRAMS\LDWord\卸载 LDWord.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortCut "$SMPROGRAMS\LDWord\官方网站.lnk" "https://dicad.cn"
  CreateShortCut "$DESKTOP\LDWord.lnk" "$INSTDIR\LDWord.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LDWord" "DisplayName" "LDWord"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LDWord" "DisplayVersion" "1.0.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LDWord" "Publisher" "LUODA"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LDWord" "URLInfoAbout" "https://dicad.cn"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LDWord" "DisplayIcon" "$INSTDIR\LDWord.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LDWord" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LDWord" "InstallLocation" "$INSTDIR"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LDWord" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LDWord" "NoRepair" 1
  WriteRegStr HKLM "Software\LDWord" "InstallDir" "$INSTDIR"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$DESKTOP\LDWord.lnk"
  RMDir /r "$SMPROGRAMS\LDWord"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\LDWord"
  DeleteRegKey HKLM "Software\LDWord"
  RMDir "$INSTDIR"
SectionEnd
