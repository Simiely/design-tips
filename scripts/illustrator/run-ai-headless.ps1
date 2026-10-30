# run-ai-headless.ps1 — Start Illustrator scripts headless, reliably.
#
# Solves the classic startup failure: when an old Illustrator instance is still
# shutting down, `Illustrator.exe -r script.jsx` pops a one-off
# "File not found" dialog (with the drive letter missing), or the new command
# is handed to the stale instance and the script never runs at all
# (process alive, CPU idle, no log file).
#
# This runner: kills stale instances -> waits until they are really gone ->
# launches -> polls the log for "done" -> returns a meaningful exit code.
#
# NOTE: keep this file pure ASCII. Windows PowerShell 5.1 reads .ps1 as ANSI
# unless it has a UTF-8 BOM, so non-ASCII strings can break parsing.
#
# IMPORTANT: Illustrator may pop a one-off "File not found" dialog for the -r
# argument even though the script is found and executed fine. That dialog is
# NOISE. Do NOT close Illustrator because of it - killing the app is what
# actually interrupts the script. The only reliable success signal is the log
# file containing "done".
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File run-ai-headless.ps1 `
#       -Jsx "D:\path\to\convert-to-ai.jsx" -Log "D:\path\to\_ailog.txt" -TimeoutSec 600
#
# Options:
#   -NoKill        do not kill existing instances before launch
#   -WaitExit      wait for Illustrator to exit after the script finishes
#   -KeepLog       do not delete an existing log before launch
#   -KillOnTimeout kill Illustrator on timeout (off by default: a running
#                  script may still be working, e.g. opening a large SVG)
#
# Exit codes: 0 ok | 2 bad arguments/file | 3 stale instance will not die
#             4 script reported ERROR | 5 timeout waiting for "done"
#             (6 = timeout and -KillOnTimeout was requested)

param(
  [Parameter(Mandatory=$true)][string]$Jsx,
  [Parameter(Mandatory=$true)][string]$Log,
  [int]$TimeoutSec = 900,
  [switch]$NoKill,
  [switch]$WaitExit,
  [switch]$KeepLog,
  [switch]$KillOnTimeout
)

$ErrorActionPreference = "Stop"
$ai = "C:\Program Files\Adobe\Adobe Illustrator 2026\Support Files\Contents\Windows\Illustrator.exe"

if (-not (Test-Path $ai)) { Write-Host "[run] Illustrator.exe not found: $ai"; exit 2 }
if (-not (Test-Path $Jsx)) { Write-Host "[run] script not found: $Jsx"; exit 2 }

function Get-AIProcs { @(Get-Process Illustrator -ErrorAction SilentlyContinue) }

# 1) Clean up: make sure no stale instance survives (it can steal the -r handoff)
if (-not $NoKill) {
  $procs = Get-AIProcs
  if ($procs.Count -gt 0) {
    Write-Host "[run] killing $($procs.Count) existing Illustrator process(es)"
    $procs | ForEach-Object { try { $_.Kill() } catch {} }
    for ($i = 0; $i -lt 30; $i++) {
      if ((Get-AIProcs).Count -eq 0) { break }
      Start-Sleep -Milliseconds 500
    }
    if ((Get-AIProcs).Count -gt 0) {
      Write-Host "[run] stale instance still running, close it manually and retry"
      exit 3
    }
    Write-Host "[run] stale instances cleared"
  }
}

# 2) Clear the log: its presence is the most reliable proof that the script ran
if (-not $KeepLog -and (Test-Path $Log)) { Remove-Item $Log -Force }

# 3) Stage the script on the SAME drive as Illustrator.
#    Measured behaviour (2026-10-30, Illustrator 2026 / build 30, Windows):
#    launching with a path on another drive (e.g. D:\...) makes Illustrator pop a
#    MODAL "File not found" box (the path is even shown without its drive letter)
#    and the script only starts after that box is dismissed -> the run stalls.
#    With the script on Illustrator's own drive (C:) the script runs straight away
#    with no dialog. So always stage to %SystemDrive% before launching.
$stageDir = Join-Path $env:SystemDrive "ai\jobs"
New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
$staged = Join-Path $stageDir ([IO.Path]::GetFileName($Jsx))
Copy-Item $Jsx $staged -Force
Write-Host "[run] staged script -> $staged"

# 4) Launch (-r runs the script; the script should call app.quit() when finished)
Write-Host "[run] launching Illustrator with -r $staged"
Start-Process -FilePath $ai -ArgumentList @("-r", $staged) | Out-Null

# 4) Poll the log for done / ERROR
$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
  if (Test-Path $Log) {
    $content = Get-Content $Log -Raw -ErrorAction SilentlyContinue
    if ($content -match "done") {
      Write-Host "[run] done"
      if ($WaitExit) { while ((Get-AIProcs).Count -gt 0) { Start-Sleep -Seconds 2 } }
      exit 0
    }
    if ($content -match "ERROR") {
      Write-Host "[run] script reported ERROR:"
      Write-Host $content
      exit 4
    }
  }
  Start-Sleep -Seconds 2
}

Write-Host "[run] timeout after ${TimeoutSec}s without 'done'"
if (Test-Path $Log) { Write-Host "--- log ---"; Get-Content $Log }
Write-Host "[run] NOTE: Illustrator may still be working (e.g. opening a large SVG). It is NOT killed by default - killing it is what actually breaks the run. Re-check the log, or raise -TimeoutSec."
if ($KillOnTimeout) {
  Write-Host "[run] -KillOnTimeout given: killing Illustrator"
  Get-AIProcs | ForEach-Object { try { $_.Kill() } catch {} }
  exit 6
}
exit 5
