' qq-bridge desktop entry: ensure console is up, then open it in the browser
Option Explicit
Dim sh, fso, root, code
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

' console on 8089?
code = sh.Run("cmd /c netstat -ano | findstr "":8089"" | findstr LISTENING", 0, True)

If code <> 0 Then
    sh.CurrentDirectory = root
    sh.Run """" & root & "\.venv\Scripts\pythonw.exe"" console.py", 0, False
    WScript.Sleep 2500
End If

sh.Run "http://127.0.0.1:8089", 1, False
