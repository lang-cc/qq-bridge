' qq-bridge desktop entry: make sure the bot service is up, then open the web console (8088/admin).
' Only two back ends exist: the web console and the NapCat panel on 6099. No desktop GUI panel any more.
Option Explicit
Dim sh, fso, root, code, token, url, f, line, parts, i

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

code = sh.Run("cmd /c netstat -ano | findstr "":8088"" | findstr LISTENING", 0, True)

If code <> 0 Then
    If fso.FileExists(root & "\.venv\Scripts\pythonw.exe") And fso.FileExists(root & "\main_nb.py") Then
        sh.CurrentDirectory = root
        sh.Run """" & root & "\.venv\Scripts\pythonw.exe"" main_nb.py", 0, False
        For i = 1 To 15
            WScript.Sleep 2000
            code = sh.Run("cmd /c netstat -ano | findstr "":8088"" | findstr LISTENING", 0, True)
            If code = 0 Then Exit For
        Next
    End If
End If

If code <> 0 Then
    MsgBox "The bot service is not running." & vbCrLf & vbCrLf & _
           "Check: " & root & "\logs\stderr.log" & vbCrLf & _
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
            token = Replace(token, "'", "")
            token = Replace(token, """", "")
        End If
    Loop
    f.Close
End If
On Error GoTo 0

url = "http://127.0.0.1:8088/admin"
If token <> "" Then url = url & "?token=" & token

sh.Run url, 1, False
