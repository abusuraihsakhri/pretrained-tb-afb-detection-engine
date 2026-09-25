' ==========================================================================
' TB-AFB Research - Desktop Shortcut Installer
' Run this ONCE to place branded icons on the Desktop.
' ==========================================================================

Dim oShell, oFSO, sRoot, sDesktop, oLink

Set oShell  = CreateObject("WScript.Shell")
Set oFSO    = CreateObject("Scripting.FileSystemObject")

sRoot   = oFSO.GetParentFolderName(WScript.ScriptFullName)
sDesktop = oShell.SpecialFolders("Desktop")

' --- Create the LAUNCH shortcut ---
Set oLink = oShell.CreateShortcut(sDesktop & "\TB-AFB Research.lnk")
oLink.TargetPath       = "wscript.exe"
oLink.Arguments        = """" & sRoot & "\Launch_App.vbs"""
oLink.WorkingDirectory = sRoot
oLink.Description      = "Local TB-AFB research inference and annotation queue"
oLink.WindowStyle      = 1
oLink.IconLocation     = sRoot & "\05_DEPLOYMENT\assets\app_icon.ico"
oLink.Save

' --- Create the STOP shortcut ---
Set oLink = oShell.CreateShortcut(sDesktop & "\Stop TB-AFB Research.lnk")
oLink.TargetPath       = "wscript.exe"
oLink.Arguments        = """" & sRoot & "\Stop_App.vbs"""
oLink.WorkingDirectory = sRoot
oLink.Description      = "Stop the exact local TB-AFB research API process"
oLink.WindowStyle      = 1
oLink.IconLocation     = sRoot & "\05_DEPLOYMENT\assets\app_icon.ico"
oLink.Save

MsgBox "Shortcuts installed successfully!" & vbCrLf & vbCrLf & _
       "You will now find two icons on your Desktop:" & vbCrLf & _
       "  1.  'TB-AFB Research'  (Launch)" & vbCrLf & _
       "  2.  'Stop TB-AFB Research'  (Shutdown)" & vbCrLf & vbCrLf & _
       "Double-click 'TB-AFB Research' to start the local interface.", _
       vbInformation, "Installation Complete"

Set oShell = Nothing
Set oFSO   = Nothing
