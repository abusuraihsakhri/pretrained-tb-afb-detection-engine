' ==========================================================================
' TB Pathology Intelligence - Silent Kiosk Launcher (FIXED)
' Starts the FastAPI backend silently and opens the UI in kiosk mode.
' ==========================================================================

Dim oShell, oFSO, sRoot, sPython, sBrowserPath

Set oShell = CreateObject("WScript.Shell")
Set oFSO   = CreateObject("Scripting.FileSystemObject")

' Resolve project root (same folder as this script)
sRoot = oFSO.GetParentFolderName(WScript.ScriptFullName)

' Set working directory to project root FIRST
oShell.CurrentDirectory = sRoot

' --- Resolve correct Python (venv first, then system python.exe) ---
' NOTE: Using python.exe NOT pythonw.exe — pythonw breaks uvicorn module loading
Dim sVenvPython
sVenvPython = sRoot & "\venv\Scripts\python.exe"
If oFSO.FileExists(sVenvPython) Then
    sPython = """" & sVenvPython & """"
Else
    sPython = "python"
End If

' --- Boot the FastAPI server via hidden cmd window ---
' cmd /c keeps the process alive; window style 0 = fully hidden
Dim sCmd
sCmd = "cmd /c " & sPython & " -m uvicorn 05_DEPLOYMENT.api.server:app --host 127.0.0.1 --port 8001"
oShell.Run sCmd, 0, False

' --- Wait for server to respond (max 40 seconds, 1-second polling) ---
Dim oHTTP, iRetry, bReady
Set oHTTP = CreateObject("MSXML2.XMLHTTP")
bReady = False

For iRetry = 1 To 40
    WScript.Sleep 1000
    On Error Resume Next
    oHTTP.Open "GET", "http://127.0.0.1:8001/api/v1/stats", False
    oHTTP.Send
    If Err.Number = 0 And oHTTP.Status = 200 Then
        bReady = True
        Exit For
    End If
    Err.Clear
    On Error GoTo 0
Next

If Not bReady Then
    MsgBox "TB Pathology Intelligence failed to start after 40 seconds." & vbCrLf & vbCrLf & _
           "Quick Fix: Run 'Start_Detection_Engine.bat' to see the exact error." & vbCrLf & _
           "Ensure 'pip install -r requirements.txt' was completed.", _
           vbCritical, "Launch Failed"
    WScript.Quit 1
End If

' --- Find browser and open in kiosk mode ---
Dim sBrowser
sBrowser = ""

' Try Microsoft Edge first (always present on Windows 10/11)
Dim sEdge
sEdge = oShell.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & _
        "\Microsoft\Edge\Application\msedge.exe"
If oFSO.FileExists(sEdge) Then
    sBrowser = """" & sEdge & """"
End If

' Fallback: try Chrome
If sBrowser = "" Then
    Dim sChrome
    sChrome = oShell.ExpandEnvironmentStrings("%ProgramFiles%") & _
              "\Google\Chrome\Application\chrome.exe"
    If oFSO.FileExists(sChrome) Then
        sBrowser = """" & sChrome & """"
    End If
End If

If sBrowser <> "" Then
    ' Kiosk mode: full screen, no address bar, no tabs
    oShell.Run sBrowser & " --kiosk --app=http://127.0.0.1:8001/ui/ " & _
               "--new-window --disable-extensions --no-default-browser-check", 1, False
Else
    ' Last resort: just open default browser normally
    oShell.Run "rundll32 url.dll,FileProtocolHandler http://127.0.0.1:8001/ui/", 1, False
End If

Set oShell = Nothing
Set oFSO   = Nothing
Set oHTTP  = Nothing
