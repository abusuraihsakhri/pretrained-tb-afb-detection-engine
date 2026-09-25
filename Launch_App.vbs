' TB-AFB Research UI launcher.
' Starts the local-only API, records its exact PID, waits for /healthz, and opens the UI.

Option Explicit

Dim oShell, oFSO, oWMI, oStartup, oProcess
Dim sRoot, sPython, sCommand, sLogDir, sPidFile
Dim iPid, iResult, iRetry, bReady, oHTTP, oFile

Set oShell = CreateObject("WScript.Shell")
Set oFSO = CreateObject("Scripting.FileSystemObject")
sRoot = oFSO.GetParentFolderName(WScript.ScriptFullName)
oShell.CurrentDirectory = sRoot

If oFSO.FileExists(sRoot & "\.venv\Scripts\python.exe") Then
    sPython = sRoot & "\.venv\Scripts\python.exe"
ElseIf oFSO.FileExists(sRoot & "\venv\Scripts\python.exe") Then
    sPython = sRoot & "\venv\Scripts\python.exe"
Else
    sPython = "python"
End If

sLogDir = sRoot & "\06_LOGS"
If Not oFSO.FolderExists(sLogDir) Then oFSO.CreateFolder(sLogDir)
sPidFile = sLogDir & "\research_api.pid"
If oFSO.FileExists(sPidFile) Then
    MsgBox "A recorded research API process already exists. Use the Stop shortcut first.", vbExclamation, "Already running"
    WScript.Quit 1
End If

sCommand = """" & sPython & """ -m uvicorn 05_DEPLOYMENT.api.server:app --host 127.0.0.1 --port 8001 --no-server-header"
Set oWMI = GetObject("winmgmts:{impersonationLevel=impersonate}!\\.\root\cimv2")
Set oStartup = oWMI.Get("Win32_ProcessStartup").SpawnInstance_
oStartup.ShowWindow = 0
Set oProcess = oWMI.Get("Win32_Process")
iResult = oProcess.Create(sCommand, sRoot, oStartup, iPid)
If iResult <> 0 Then
    MsgBox "The local research API could not be started. WMI result: " & iResult, vbCritical, "Launch failed"
    WScript.Quit 1
End If

Set oFile = oFSO.CreateTextFile(sPidFile, True)
oFile.WriteLine CStr(iPid)
oFile.Close

Set oHTTP = CreateObject("MSXML2.XMLHTTP")
bReady = False
For iRetry = 1 To 60
    WScript.Sleep 1000
    On Error Resume Next
    oHTTP.Open "GET", "http://127.0.0.1:8001/healthz", False
    oHTTP.Send
    If Err.Number = 0 And oHTTP.Status = 200 Then
        bReady = True
        Exit For
    End If
    Err.Clear
    On Error GoTo 0
Next

If Not bReady Then
    On Error Resume Next
    oWMI.Get("Win32_Process.Handle='" & CStr(iPid) & "'").Terminate
    oFSO.DeleteFile sPidFile, True
    On Error GoTo 0
    MsgBox "The TB-AFB research API did not become ready after 60 seconds. Run Start_Detection_Engine.bat to inspect the error.", vbCritical, "Launch failed"
    WScript.Quit 1
End If

oShell.Run "http://127.0.0.1:8001/ui/", 1, False

Set oHTTP = Nothing
Set oProcess = Nothing
Set oStartup = Nothing
Set oWMI = Nothing
Set oFSO = Nothing
Set oShell = Nothing
