Option Explicit
' qq-bridge desktop entry (Windows).  ASCII only - do not put Chinese here.
'
' Double-click: make sure the bot service on 8088 is up, then open the web console
' at http://127.0.0.1:8088/admin .
'
' The protocol backend (NapCat / SnowLuma) is NOT checked here: boot.py and
' watchdog.py already handle it via qqbot/proto.py. This script only cares about
' 8088, so it keeps working whichever backend config.yaml points at.

Dim sh, fso, root, f, line, parts, token, url, i, up, pyw

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

' Is 8088 alive? Ask /status - more reliable than parsing netstat.
Function SvcUp()
    Dim http
    On Error Resume Next
    SvcUp = False
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", "http://127.0.0.1:8088/status", False
    http.Send
    If Err.Number = 0 Then
        If http.Status = 200 Then SvcUp = True
    End If
    Err.Clear
    On Error Goto 0
End Function

up = SvcUp()

If Not up Then
    pyw = root & "\.venv\Scripts\pythonw.exe"
    If fso.FileExists(pyw) And fso.FileExists(root & "\boot.py") Then
        sh.CurrentDirectory = root
        ' boot.py starts the service + protocol backend + watchdog, silently.
        sh.Run """" & pyw & """ boot.py", 0, False
        For i = 1 To 30
            WScript.Sleep 2000
            If SvcUp() Then
                up = True
                Exit For
            End If
        Next
    End If
End If

If Not up Then
    MsgBox "The bot service on 8088 did not come up." & vbCrLf & vbCrLf & _
           "Look at: " & root & "\logs\boot.log" & vbCrLf & _
           "Or run : .venv\Scripts\python.exe selfcheck.py", 48, "qq-bridge"
    WScript.Quit 1
End If

' Use http_api.token when it is set, so the browser lands straight in.
token = ""
On Error Resume Next
If fso.FileExists(root & "\config.yaml") Then
    Set f = fso.OpenTextFile(root & "\config.yaml", 1)
    Do Until f.AtEndOfStream
        line = f.ReadLine
        If InStr(line, "  token:") = 1 Then
            parts = Split(line, ":")
            token = Trim(parts(1))
            token = Replace(token, """", "")
            token = Replace(token, "'", "")
        End If
    Loop
    f.Close
End If
On Error Goto 0

url = "http://127.0.0.1:8088/admin"
If Len(token) > 0 Then url = url & "?token=" & token

sh.Run url, 1, False
