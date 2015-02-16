OutFile "BitTornado-0.4.0-w32install.exe"
Name "BitTornado 0.4.0"
SetCompressor lzma
InstallDir "$PROGRAMFILES\BitTornado"
Icon "icon_bt.ico"
UninstallIcon "icon_done.ico"
InstallDirRegKey  HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\btdownloadgui.exe" ""
DirText "Setup will install BitTornado 0.4.0 in the following folder.$\r$\n$\r$\nTo install in a different folder, click Browse and select another folder."
ShowInstDetails show
ShowUnInstDetails show

Section "MainGroup" SEC01
  SetOutPath "$INSTDIR"
  IfFileExists "$INSTDIR\_psyco.pyd" +1 +2
  delete "$INSTDIR\_psyco.pyd"
  SetOverwrite on
  File "*.exe"
  File "*.dll"
  File "*.pyd"
  File "library.zip"
  CreateDirectory "$SMPROGRAMS\BitTornado"
  CreateShortCut "$SMPROGRAMS\BitTornado\BitTornado.lnk" "$INSTDIR\btdownloadgui.exe"
#  CreateShortCut "$DESKTOP\BitTornado.lnk" "$INSTDIR\btdownloadgui.exe"
  CreateShortCut "$SMPROGRAMS\BitTornado\Uninstall.lnk" "$INSTDIR\uninst.exe"
  SetOverwrite off
SectionEnd

Section -Post
  WriteRegStr HKCR .torrent "" bittorrent
  WriteRegStr HKCR .torrent "Content Type" application/x-bittorrent
  WriteRegStr HKCR "MIME\Database\Content Type\application/x-bittorrent" Extension .torrent
  WriteRegStr HKCR bittorrent "" "TORRENT File"
  WriteRegBin HKCR bittorrent EditFlags 00000100
  WriteRegStr HKCR "bittorrent\shell" "" open
  WriteRegStr HKCR "bittorrent\shell\open\command" "" `"$INSTDIR\btdownloadgui.exe" --responsefile "%1"`

  WriteUninstaller "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\btdownloadgui.exe" "" "$INSTDIR\btdownloadgui.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BitTornado" "DisplayName" "BitTornado 0.4.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BitTornado" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BitTornado" "DisplayIcon" "$INSTDIR\btdownloadgui.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BitTornado" "DisplayVersion" "0.4.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BitTornado" "URLInfoAbout" "https://github.com/effigies/BitTornado"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BitTornado" "Publisher" "Christopher J. Markiewicz"
SectionEnd


Function un.onUninstSuccess
  HideWindow
  MessageBox MB_ICONINFORMATION|MB_OK "BitTornado 0.4.0 was successfully removed from your computer."
FunctionEnd

Function un.onInit
  MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to completely remove BitTornado 0.4.0 and all of its components?" IDYES +2
  Abort
FunctionEnd

Section Uninstall
  Delete "$SMPROGRAMS\BitTornado\BitTornado.lnk"
#  Delete "$DESKTOP\BitTornado.lnk"
  Delete "$SMPROGRAMS\BitTornado\Uninstall.lnk"
  RMDir "$SMPROGRAMS\BitTornado"
#  DeleteRegKey HKCR software\bittorrent

  push $1
  ReadRegStr $1 HKCR "bittorrent\shell\open\command" ""
  StrCmp $1 `"$INSTDIR\btdownloadgui.exe" --responsefile "%1"` 0 regnotempty
  DeleteRegKey HKCR bittorrent\shell\open
  DeleteRegKey /ifempty HKCR bittorrent\shell
  DeleteRegKey /ifempty HKCR bittorrent
  ReadRegStr $1 HKCR bittorrent\shell ""
  StrCmp $1 "" 0 regnotempty
  DeleteRegKey HKCR .torrent
  DeleteRegKey HKCR "MIME\Database\Content Type\application/x-bittorrent"
 regnotempty:
  pop $1
  RMDir /r "$INSTDIR"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BitTornado"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\App Paths\btdownloadgui.exe"
  SetAutoClose true
SectionEnd

