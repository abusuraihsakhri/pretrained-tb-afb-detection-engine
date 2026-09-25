' Stop only the exact local API process recorded by Launch_App.vbs.

Option Explicit

Dim oFSO, oWMI, oFile, oProcesses, oItem
Dim sRoot, sPidFile, sPid, sCommand, bStopped

Set oFSO = CreateObject("Scripting.FileSystemObject")
sRoot = oFSO.GetParentFolderName(WScript.ScriptFullName)
sPidFile = sRoot & "\06_LOGS\research_api.pid"

If Not oFSO.FileExists(sPidFile) Then
    MsgBox "No recorded TB-AFB research API process was found.", vbInformation, "Nothing to stop"
    WScript.Quit 0
End If

Set oFile = oFSO.OpenTextFile(sPidFile, 1)
sPid = Trim(oFile.ReadLine)
oFile.Close
If Not IsNumeric(sPid) Then
    MsgBox "The recorded PID is invalid. Delete 06_LOGS\research_api.pid after checking running processes manually.", vbCritical, "Stop cancelled"
    WScript.Quit 1
End If

Set oWMI = GetObject("winmgmts:{impersonationLevel=impersonate}!\\.\root\cimv2")
Set oProcesses = oWMI.ExecQuery("SELECT * FROM Win32_Process WHERE ProcessId=" & CLng(sPid))
bStopped = False
For Each oItem In oProcesses
    If IsNull(oItem.CommandLine) Then
        sCommand = ""
    Else
        sCommand = LCase(CStr(oItem.CommandLine))
    End If
    If InStr(sCommand, "uvicorn") > 0 And InStr(sCommand, "05_deployment.api.server:app") > 0 Then
        oItem.Terminate
        bStopped = True
    Else
        MsgBox "The recorded PID now belongs to a different process. Nothing was terminated.", vbCritical, "Stop cancelled"
        WScript.Quit 1
    End If
Next

oFSO.DeleteFile sPidFile, True
If bStopped Then
    MsgBox "The TB-AFB research API was stopped.", vbInformation, "Stopped"
Else
    MsgBox "The recorded process was no longer running. The stale PID record was removed.", vbInformation, "Already stopped"
End If

Set oProcesses = Nothing
Set oWMI = Nothing
Set oFSO = Nothing
