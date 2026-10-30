@echo off
rem ============================================================================
rem  install-ai-startup-dispatcher.cmd
rem  One-click installer for the Illustrator "Startup Scripts" dispatcher.
rem  Purpose: run Illustrator scripts with ZERO dialogs - Illustrator is
rem            launched with NO command-line file argument, so it never tries
rem            to "open" the .jsx as a document (the harmless File not found box).
rem
rem  Steps: UAC elevation -> write Startup Scripts -> create job folder ->
rem          self-test (launch AI with no args, check the dispatch log).
rem
rem  Uninstall: delete "%ProgramFiles%\Adobe\Adobe Illustrator 2026\Startup Scripts\startup-dispatcher.jsx"
rem
rem  NOTE: pure ASCII on purpose. cmd.exe may mangle non-ASCII text.
rem  NOTE: no parenthesised IF blocks on purpose - unbalanced parentheses inside
rem        them break cmd parsing with "... was unexpected at this time".
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

if not exist "%DISPATCHER%" goto :no_dispatcher

net session >nul 2>&1
if errorlevel 1 goto :need_admin

if /I "%~1"=="/install-only" goto :install_elevated

:need_admin
echo [1/4] Requesting administrator rights - please accept the UAC prompt...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs -ArgumentList '/install-only' -Wait" >nul 2>&1
if exist "%TARGET%" goto :after_install
echo [ERROR] Installation did not complete.
echo         Right-click this file and choose "Run as administrator", then try again.
echo.
echo         Or do it manually from an ADMIN terminal:
echo           mkdir "%AIROOT%\Startup Scripts"
echo           copy "%DISPATCHER%" "%TARGET%"
echo           mkdir "%JOBDIR%"
echo           start "" "%AIEXE%"    REM AI will run the dispatcher on startup
goto :pause_fail

:after_install
echo [1/4] Administrator install finished.
goto :selftest

:install_elevated
echo [2/4] Installing dispatcher into "%AIROOT%\Startup Scripts"
mkdir "%AIROOT%\Startup Scripts" >nul 2>&1
copy /Y "%DISPATCHER%" "%TARGET%" >nul
if not exist "%TARGET%" goto :install_fail
echo         OK -^> %TARGET%
exit /b 0

:install_fail
echo [ERROR] Could not write to "%TARGET%"
pause
exit /b 1

:no_dispatcher
echo [ERROR] startup-dispatcher.jsx not found next to this file:
echo         %DISPATCHER%
pause
exit /b 2

:selftest
echo.
echo [3/4] Preparing job folder: %JOBDIR%
mkdir "%JOBDIR%" >nul 2>&1

echo [4/4] Self-test - launching Illustrator with NO arguments.
echo         Expect a line "no job queued - skip" in the dispatch log below.
taskkill /IM Illustrator.exe /F >nul 2>&1
if exist "%DLOG%" del "%DLOG%" >nul 2>&1
start "" "%AIEXE%"
echo         waiting 45 seconds ...
timeout /t 45 /nobreak >nul
echo.
echo ------------------------- dispatch log -------------------------
if not exist "%DLOG%" goto :no_log
type "%DLOG%"
findstr /C:"no job queued" "%DLOG%" >nul
if errorlevel 1 goto :log_weird
echo [RESULT] PASS - Startup Scripts dispatcher executed.
goto :pass

:log_weird
echo [RESULT] CHECK - dispatch log exists but has no "no job queued" line.
goto :fail

:no_log
echo [RESULT] FAIL - no dispatch log produced, Startup Scripts did not run.
goto :fail

:pass
echo.
echo ============================================================
echo   DONE - you can now run scripts with ZERO dialogs:
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

:pause_fail
pause
exit /b 1
