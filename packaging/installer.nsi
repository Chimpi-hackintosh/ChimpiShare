Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
!include "LogicLib.nsh"

Name "ChimpiShare"
OutFile "${__FILEDIR__}\..\dist\ChimpiShare-0.1.0-Setup-x64.exe"
InstallDir "$PROGRAMFILES64\SnoopyOS Company\ChimpiShare"
InstallDirRegKey HKLM "Software\SnoopyOS Company\ChimpiShare" "InstallDir"
RequestExecutionLevel admin
VIProductVersion "0.1.0.0"
VIAddVersionKey "ProductName" "ChimpiShare"
VIAddVersionKey "CompanyName" "SnoopyOS Company"
VIAddVersionKey "FileVersion" "0.1.0"
VIAddVersionKey "FileDescription" "ChimpiShare Setup"

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "PortugueseBR"

LangString DesktopShortcut ${LANG_ENGLISH} "Desktop shortcut"
LangString DesktopShortcut ${LANG_PORTUGUESEBR} "Atalho na área de trabalho"
LangString X64Required ${LANG_ENGLISH} "This installer requires Windows x64"
LangString X64Required ${LANG_PORTUGUESEBR} "Este instalador exige Windows x64"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "$(X64Required)"
    Abort
  ${EndIf}
  SetRegView 64
  SetShellVarContext all
  ReadRegStr $0 HKLM "Software\SnoopyOS Company\ChimpiShare" "InstallDir"
  ${If} $0 != ""
    StrCpy $INSTDIR $0
  ${EndIf}
FunctionEnd

Section "ChimpiShare" Main
  SectionIn RO
  SetOutPath "$INSTDIR"
  File /r "${__FILEDIR__}\..\dist\ChimpiShare\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\SnoopyOS Company"
  CreateShortcut "$SMPROGRAMS\SnoopyOS Company\ChimpiShare.lnk" "$INSTDIR\ChimpiShare.exe"
  WriteRegStr HKLM "Software\SnoopyOS Company\ChimpiShare" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChimpiShare" "DisplayName" "ChimpiShare"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChimpiShare" "DisplayVersion" "0.1.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChimpiShare" "Publisher" "SnoopyOS Company"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChimpiShare" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChimpiShare" "DisplayIcon" "$INSTDIR\ChimpiShare.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChimpiShare" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChimpiShare" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChimpiShare" "NoRepair" 1
SectionEnd

Section /o "$(DesktopShortcut)" Desktop
  CreateShortcut "$DESKTOP\ChimpiShare.lnk" "$INSTDIR\ChimpiShare.exe"
SectionEnd

Section "Uninstall"
  SetRegView 64
  SetShellVarContext all
  Delete "$DESKTOP\ChimpiShare.lnk"
  Delete "$SMPROGRAMS\SnoopyOS Company\ChimpiShare.lnk"
  RMDir "$SMPROGRAMS\SnoopyOS Company"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ChimpiShare"
  DeleteRegKey HKLM "Software\SnoopyOS Company\ChimpiShare"
  RMDir /r "$INSTDIR"
  ; User configuration and received files are deliberately preserved.
SectionEnd
