' qq-bridge silent start: service + NapCat + watchdog (no console window). ASCII only.
Option Explicit
Dim sh, fso, root
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

' boot.py starts the service, NapCat, the watchdog, and opens a QR window
' automatically when the QQ session has dropped.
sh.CurrentDirectory = root
sh.Run """" & root & "\.venv\Scripts\pythonw.exe"" boot.py", 0, False
