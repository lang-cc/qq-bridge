Option Explicit
' qq-bridge desktop entry.
' One icon does everything: make sure the service (8088) and NapCat (6099) are up,
' then open the web console at 8088/admin. There is no desktop GUI any more.
Dim sh, fso, root, code, token, url, f, line, parts, i, need
Dim pyw, n8088, n6099

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

Function PortUp(p)
    Dim rc
    rc = sh.Run("cmd /c netstat -ano | findstr "":" & p & """ | findstr LISTENING", 0, True)
    PortUp = (rc = 0)
End Function

n8088 = PortUp(8088)
n6099 = PortUp(6099)

If (Not n8088) Or (Not n6099) Then
    pyw = root & "\.venv\Scripts\pythonw.exe"
    If fso.FileExists(pyw) And fso.FileExists(root & "\boot.py") Then
        sh.CurrentDirectory = root
        ' boot.py: start service + NapCat + watchdog, and pop the QR window if logged out
        sh.Run """" & pyw & """ boot.py", 0, False
        For i = 1 To 40
            WScript.Sleep 3000
            If PortUp(8088) Then Exit For
        Next
    End If
End If

If Not PortUp(8088) Then
    MsgBox "The bot service did not start." & vbCrLf & vbCrLf & _
           "Check: " & root & "\logs\boot.log" & vbCrLf & _
           "Or run: .venv\Scripts\python.exe selfcheck.py", 48, "qq-bridge"
    WScript.Quit 1
End If

' use the token from config.yaml (http_api.token) when one is set
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
