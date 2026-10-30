@echo off
rem ============================================================================
rem  install-ai-startup-dispatcher.cmd
rem  One-click installer for the Illustrator "Startup Scripts" dispatcher.
rem  Purpose: makes it possible to run Illustrator scripts with ZERO dialogs,
rem            because Illustrator is launched with NO command-line file
rem            argument (it would otherwise try to "open" the .jsx as a
rem            document and pop a harmless "File not found" box).
rem
rem  What it does:
rem    1) asks for administrator rights (UAC) - needed to write into Program Files
rem    2) creates "C:\Program Files\Adobe\Adobe Illustrator 2026\Startup Scripts\"
rem    3) copies startup-dispatcher.jsx there
rem    4) creates %USERPROFILE%\Documents\Adobe\Scripts (trusted folder for jobs)
rem    5) self-test: launches Illustrator with no arguments and checks whether
rem       the dispatcher really executed (writes _ai_dispatch.log)
rem
rem  Uninstall: delete "%ProgramFiles%\Adobe\Adobe Illustrator 2026\Startup Scripts\startup-dispatcher.jsx"
rem
rem  NOTE: keep this file ASCII-only. cmd.exe may mangle non-ASCII text.
rem ============================================================================
setlocal enabledelayedexpansion

set "AIROOT=C:\Program Files\Adobe\Adobe Illustrator 2026"
set "AIEXE=%AIROOT%\Support Files\Contents\Windows\Illustrator.exe"
set "DISPATCHER=%~dp0startup-dispatcher.jsx"
set "JOBDIR=%USERPROFILE%\Documents\Adobe\Scripts"
set "DLOG=%JOBDIR%\_ai_dispatch.log"
set "TARGET=%AIROOT%\Startup Scripts\startup-dispatcher.jsx"

echo.
echo ============================================================
echo   Illustrator Startup Scripts dispatcher - installer
echo ============================================================
echo.

if not exist "%DISPATCHER%" (
  echo [ERROR] startup-dispatcher.jsx not found next to this file:
  echo         %DISPATCHER%
  pause
  exit /b 2
)

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo [1/4] Requesting administrator rights (UAC prompt)...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs -ArgumentList '/install-only' -Wait" >nul 2>&1
  if not exist "%TARGET%" (
    echo [ERROR] Installation did not complete. Right-click this file and choose
    echo         "Run as administrator", or run it from an elevated terminal.
    pause
    exit /b 1
  )
  goto :selftest
)

if /I "%~1"=="/install-only" goto :elevated

:elevated
echo [2/4] Installing dispatcher into "%AIROOT%\Startup Scripts\"
mkdir "%AIROOT%\Startup Scripts" >nul 2>&1
copy /Y "%DISPATCHER%" "%TARGET%" >nul
if not exist "%TARGET%" (
  echo [ERROR] Could not write to "%TARGET%"
  pause
  exit /b 1
)
echo         OK -^> %TARGET%
goto :done_elevated

:done_elevated
exit /b 0

:selftest
echo.
echo [3/4] Preparing job folder: %JOBDIR%
mkdir "%JOBDIR%" >nul 2>&1

echo [4/4] Self-test: launching Illustrator with NO arguments ...
echo         (a "no job queued - skip" line in the dispatch log = dispatcher works)
taskkill /IM Illustrator.exe /F >nul 2>&1
if exist "%DLOG%" del "%DLOG%" >nul 2>&1
start "" "%AIEXE%"
echo         waiting 45 seconds ...
timeout /t 45 /nobreak >nul
echo.
echo ------------------------- dispatch log -------------------------
if not exist "%DLOG%" goto :nolog
type "%DLOG%"
findstr /C:"no job queued" "%DLOG%" >nul
if errorlevel 1 goto :logweird
echo [RESULT] PASS - Startup Scripts dispatcher executed.
goto :pass

:logweird
echo [RESULT] CHECK - dispatch log exists but has no 'no job queued' line; see above.
goto :fail

:nolog
echo [RESULT] FAIL - no dispatch log produced; Startup Scripts did not run.
goto :fail

:pass
echo.
echo ============================================================
echo   DONE. From now on you can run scripts with ZERO dialogs:
echo.
echo   powershell -ExecutionPolicy Bypass -File ^<repo^>\scripts\illustrator\run-ai-job.ps1 ^
echo       -Job "D:\path\to\your-script.jsx" -Log "D:\path\to\log.txt"
echo ============================================================
echo.
pause
exit /b 0

:fail
echo.
echo If Startup Scripts did not fire, use the COM route instead:
echo   cscript //nologo ^<repo^>\scripts\illustrator\run-ai-headless.vbs ^
echo       "D:\path\to\your-script.jsx" "D:\path\to\log.txt" 600
echo.
pause
exit /b 1
