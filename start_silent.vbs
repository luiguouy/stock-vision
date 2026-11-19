' ============================================================
' StockVision 静默启动器
' 用 wscript 启动，全程不产生任何控制台窗口（无黑框、无闪烁）
' 后端日志：stage_one\backend\logs\desktop.log
' ============================================================
Option Explicit

Dim sh, fso, base, pyw, target
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

base = fso.GetParentFolderName(WScript.ScriptFullName)
target = base & "\stage_one\backend\desktop_main.py"
pyw = base & "\.venv\Scripts\pythonw.exe"

If Not fso.FileExists(pyw) Then pyw = "pythonw.exe"

sh.CurrentDirectory = base
sh.Run """" & pyw & """ """ & target & """", 0, False
