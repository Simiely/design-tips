# install-startup-dispatcher.ps1 — 安装启动脚本派发器（一次性，需管理员）
#
# 把 startup-dispatcher.jsx 复制到 Illustrator 安装目录的 "Startup Scripts" 文件夹，
# 之后只要 AI 启动就会自动执行派发器 → 排队任务即可被自动执行 → 全程零命令行参数、零弹窗。
#
# 用法（右键"以管理员身份运行" PowerShell，或在本脚本上执行）：
#   powershell -ExecutionPolicy Bypass -File install-startup-dispatcher.ps1
#
# 卸载：把脚本末尾输出的 Startup Scripts 目录里的 startup-dispatcher.jsx 删掉即可。

$ErrorActionPreference = "Stop"
$src = Join-Path $PSScriptRoot "startup-dispatcher.jsx"
$aiRoot = "C:\Program Files\Adobe\Adobe Illustrator 2026"
$target = Join-Path $aiRoot "Startup Scripts"

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Path $src)) { Write-Host "[install] source not found: $src"; exit 2 }
if (-not (Test-Admin)) {
  Write-Host "[install] need administrator - relaunching elevated ..."
  try {
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList @("-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"")
    Write-Host "[install] elevated window launched; check it for the result."
  } catch {
    Write-Host "[install] elevation failed: $($_.Exception.Message)"
    Write-Host "[install] alternative: manually create the folder and copy the file:"
    Write-Host "           mkdir `"$target`""
    Write-Host "           copy `"$src`" `"$target`""
  }
  exit 0
}

if (-not (Test-Path $aiRoot)) {
  Write-Host "[install] Illustrator install dir not found: $aiRoot"
  Write-Host "[install] adjust `$aiRoot in this script to your version, then re-run."
  exit 2
}

New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item $src -Destination (Join-Path $target "startup-dispatcher.jsx") -Force

Write-Host "[install] OK ->" (Join-Path $target "startup-dispatcher.jsx")
Write-Host "[install] verify: open the file above; it should exist."
Write-Host "[install] uninstall: delete that file."
Write-Host "[install] next: use run-ai-job.ps1 to queue jobs (AI is launched with no arguments)."
