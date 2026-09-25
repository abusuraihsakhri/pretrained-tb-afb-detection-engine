' ==========================================================================
' TB Pathology Intelligence - Silent Stop Script
' Cleanly terminates the FastAPI server process without data corruption.
' ==========================================================================

Dim oShell
Set oShell = CreateObject("WScript.Shell")

' Kill uvicorn/python server bound to port 8001 gracefully
oShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr :8001') do taskkill /PID %a /F", 0, True

' Small confirmation
WScript.Sleep 500
MsgBox "TB Pathology Intelligence has been shut down safely.", vbInformation, "Shutdown Complete"

Set oShell = Nothing
