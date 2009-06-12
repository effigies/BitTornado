# Written by Bram Cohen
# see LICENSE.txt for license information

Outfile completedir.exe
Name completedir
SilentInstall silent
InstallDir "$PROGRAMFILES\completedir\"
Section "Install"
  WriteUninstaller "$INSTDIR\uninstall.exe"
  SetOutPath $INSTDIR
  File btcompletedirgui.exe
  File *.pyd
  File *.dll
  CreateShortCut "$STARTMENU\Programs\completedir.lnk" "$INSTDIR\btcompletedirgui.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CompleteDir" "DisplayName" "BitTorrent complete dir 1.0.1"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CompleteDir" "UninstallString" '"$INSTDIR\uninstall.exe"'
  MessageBox MB_OK "Complete dir has been successfully installed! Run it under the Programs in the Start Menu."
SectionEnd

Section "Uninstall"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CompleteDir"
  Delete "$STARTMENU\Programs\completedir.lnk"
  RMDir /r "$INSTDIR"
SectionEnd
