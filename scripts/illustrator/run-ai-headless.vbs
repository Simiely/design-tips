' run-ai-headless.vbs — Illustrator 无头执行脚本（COM 路线，零弹窗）
'
' 与 "Illustrator.exe -r x.jsx" 的区别与优势：
'   1) 不经命令行传路径 → 不会触发 "File not found"（AI 把 .jsx 当文档打开导致的弹窗）
'   2) 可以真正等待脚本执行完成 → 退出码可信
'   3) 配合一次性设置 ShowExternalJSXWarning=false（见 suppress-external-warning.jsx）
'      → 连"是否允许运行脚本"的安全警告也不再弹
'
' 官方/社区依据：Adobe 社区 "Run existing script from command line or any other automated way"
'   Set appRef = CreateObject("Illustrator.Application")
'   appRef.DoJavaScriptFile scriptdir & "\cron.jsxbin", Array(arg1, arg2)
'   并注明：DoJavaScriptFile 前需 sleep ~10 秒，等 Illustrator 启动完成，否则脚本不执行。
'
' 用法：
'   cscript //nologo run-ai-headless.vbs <script.jsx> [logFile] [timeoutSeconds]
' 退出码：0 成功 | 2 参数/文件不存在 | 3 超时 | 4 脚本内部 ERROR
'
' 注意：本文件保持纯 ASCII，避免编码问题。

Option Explicit

Dim fso, shell, appRef, jsxPath, logPath, timeoutSec, script, logText, startTime, waited
Dim aiExe, shellCmd

If WScript.Arguments.Count < 1 Then
  WScript.Echo "usage: cscript //nologo run-ai-headless.vbs <script.jsx> [logFile] [timeoutSec]"
  WScript.Quit 2
End If

jsxPath  = WScript.Arguments(0)
logPath  = "D:\workbuddy\2026-10-30-10-34-27\pdfimg\_vbs_log.txt"
timeoutSec = 600
If WScript.Arguments.Count >= 2 Then logPath = WScript.Arguments(1)
If WScript.Arguments.Count >= 3 Then timeoutSec = CLng(WScript.Arguments(2))

Set fso = CreateObject("Scripting.FileSystemObject")
If Not fso.FileExists(jsxPath) Then
  WScript.Echo "[vbs] script not found: " & jsxPath
  WScript.Quit 2
End If

' 清掉旧日志：日志是否生成 = 脚本是否真的执行的判据
If fso.FileExists(logPath) Then fso.DeleteFile logPath, True

' 先确保没有残留实例（否则交接可能失败）
shellCmd = "taskkill /IM Illustrator.exe /F >nul 2>&1"
shell.Run shellCmd, 0, False
WScript.Sleep 3000

WScript.Echo "[vbs] attaching to Illustrator via COM ..."
On Error Resume Next
Set appRef = CreateObject("Illustrator.Application")
If Err.Number <> 0 Then
  WScript.Echo "[vbs] COM attach failed: " & Err.Description
  WScript.Quit 2
End If
On Error GoTo 0

' 官方社区结论：DoJavaScriptFile 之前必须等 Illustrator 启动完成（约 10 秒），否则脚本不执行
WScript.Echo "[vbs] waiting 10s for Illustrator to finish booting ..."
WScript.Sleep 10000

WScript.Echo "[vbs] dispatching: " & jsxPath
Err.Clear
On Error Resume Next
appRef.DoJavaScriptFile jsxPath, Array()
If Err.Number <> 0 Then
  WScript.Echo "[vbs] DoJavaScriptFile error: " & Err.Description
  WScript.Quit 4
End If
On Error GoTo 0
WScript.Echo "[vbs] dispatched, waiting for log 'done' ..."

startTime = Now
Do
  If fso.FileExists(logPath) Then
    Set script = fso.OpenTextFile(logPath, 1)
    logText = script.ReadAll
    script.Close
    If InStr(logText, "done") > 0 Then
      WScript.Echo "[vbs] done"
      WScript.Quit 0
    End If
    If InStr(logText, "ERROR") > 0 Then
      WScript.Echo "[vbs] script reported ERROR:"
      WScript.Echo logText
      WScript.Quit 4
    End If
  End If
  WScript.Sleep 2000
  waited = (Now - startTime) * 24 * 60 * 60
Loop While waited < timeoutSec

WScript.Echo "[vbs] timeout after " & timeoutSec & "s without 'done'"
WScript.Quit 3
