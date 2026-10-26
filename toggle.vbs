' qq-bridge: double-click opens the control panel (start / QR login / watchdog / stop). ASCII only.
Option Explicit
Dim sh, fso, root
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

sh.CurrentDirectory = root
sh.Run """" & root & "\.venv\Scripts\pythonw.exe"" panel.py", 0, False
