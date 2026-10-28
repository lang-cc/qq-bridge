' 用当前登录用户的正常权限静默启动 SnowLuma。
' 必须从资源管理器/双击方式启动：从受限环境（低完整性）启动的 node.exe
' 注入不了 QQ（Medium 完整性），面板会报「Node 完整性过低」。
Option Explicit
Dim sh, fso, home
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
home = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = home
If fso.FileExists(home & "\node.exe") Then
  sh.Run """" & home & "\node.exe"" index.mjs", 0, False
Else
  sh.Run "node index.mjs", 0, False
End If
