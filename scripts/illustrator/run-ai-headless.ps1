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
# Usage:
#   powershell -ExecutionPolicy Bypass -File run-ai-headless.ps1 `
#       -Jsx "D:\path\to\convert-to-ai.jsx" -Log "D:\path\to\_ailog.txt" -TimeoutSec 600
#
# Options:
#   -NoKill    do not kill existing instances (launch + poll only)
#   -WaitExit  wait for Illustrator to exit after the script finishes
#   -KeepLog   do not delete an existing log before launch
#
# Exit codes: 0 ok | 2 bad arguments/file | 3 stale instance will not die
#             4 script reported ERROR | 5 timeout waiting for "done"

param(
  [Parameter(Mandatory=$true)][string]$Jsx,
  [Parameter(Mandatory=$true)][string]$Log,
  [int]$TimeoutSec = 600,
  [switch]$NoKill,
  [switch]$WaitExit,
  [switch]$KeepLog
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

# 3) Launch (-r runs the script; the script should call app.quit() when finished)
Write-Host "[run] launching: $Jsx"
Start-Process -FilePath $ai -ArgumentList @("-r", $Jsx) | Out-Null

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
Write-Host "[run] if the log exists but has no 'done', the script is stuck (check for a modal dialog; keep app.userInteractionLevel = DONTDISPLAYALERTS)."
exit 5
