# run-ai-job.ps1 — 零弹窗运行队列任务（配合 startup-dispatcher.jsx）
#
# 原理：AI 启动时会自动执行 "Startup Scripts" 里的派发器；本脚本把任务 .jsx 排进
#       %USERPROFILE%\Documents\Adobe\Scripts\_ai_job.jsx，然后【不带任何参数】启动 AI，
#       派发器发现任务就执行它 —— 全程没有命令行文件参数，因此不会出现 "File not found" 弹窗，
#       也不再需要 COM。
#
# 前置：先以管理员身份运行一次 install-startup-dispatcher.ps1。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File run-ai-job.ps1 -Job "D:\path\to\convert-to-ai.jsx" -Log "D:\path\to\_ailog.txt" -TimeoutSec 540
#
# 退出码：0 成功 | 2 参数/文件不存在 | 3 任务被标记为已处理（.done 残留） | 5 超时

param(
  [Parameter(Mandatory=$true)][string]$Job,
  [Parameter(Mandatory=$true)][string]$Log,
  [int]$TimeoutSec = 540,
  [switch]$KeepAlive
)

$ErrorActionPreference = "Stop"
$ai = "C:\Program Files\Adobe\Adobe Illustrator 2026\Support Files\Contents\Windows\Illustrator.exe"
$qdir = Join-Path $env:USERPROFILE "Documents\Adobe\Scripts"
$jobTarget = Join-Path $qdir "_ai_job.jsx"
$markFile  = Join-Path $qdir "_ai_job.done"

if (-not (Test-Path $Job)) { Write-Host "[job] job script not found: $Job"; exit 2 }
if (-not (Test-Path $ai)) { Write-Host "[job] Illustrator.exe not found: $ai"; exit 2 }

New-Item -ItemType Directory -Force -Path $qdir | Out-Null
Copy-Item $Job -Destination $jobTarget -Force
if (Test-Path $markFile) { Remove-Item $markFile -Force }   # 清去重标记，允许本次任务被执行
if (Test-Path $Log) { Remove-Item $Log -Force }

# 清场：避免旧实例占住导致启动脚本不触发
Get-Process Illustrator -ErrorAction SilentlyContinue | ForEach-Object { try { $_.Kill() } catch {} }
for ($i = 0; $i -lt 20; $i++) {
  if (-not (Get-Process Illustrator -ErrorAction SilentlyContinue)) { break }
  Start-Sleep -Milliseconds 500
}

# 关键：不带任何参数启动 AI —— 派发器会自动拾取任务
Write-Host "[job] launching Illustrator (no args) ..."
Start-Process -FilePath $ai | Out-Null

$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
  if (Test-Path $Log) {
    $content = Get-Content $Log -Raw -ErrorAction SilentlyContinue
    if ($content -match "done") {
      Write-Host "[job] done"
      if (-not $KeepAlive) { Get-Process Illustrator -ErrorAction SilentlyContinue | ForEach-Object { try { $_.Kill() } catch {} } }
      Remove-Item $jobTarget -Force -ErrorAction SilentlyContinue
      exit 0
    }
    if ($content -match "ERROR") {
      Write-Host "[job] job reported ERROR:"; Write-Host $content
      exit 4
    }
  }
  Start-Sleep -Seconds 2
}

Write-Host "[job] timeout after ${TimeoutSec}s. Check $Log and the dispatch log:"
Write-Host "        $qdir\_ai_dispatch.log"
Write-Host "[job] NOTE: AI was NOT killed (the job may still be working)."
exit 5
