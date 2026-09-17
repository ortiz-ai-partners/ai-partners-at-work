@echo off
REM osanpo claude - start the receive server (Windows 11)
REM Called by Task Scheduler at logon. Can also be run by hand.
REM Secrets live in osanpo\windows\osanpo.env (not in git). Keep this file ASCII-only:
REM cmd.exe reads .bat files in the legacy code page, so Japanese text here breaks.

chcp 65001 >nul
cd /d "%~dp0.."

if exist "%~dp0osanpo.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0osanpo.env") do set "%%A=%%B"
)

if "%OSANPO_TOKEN%"=="" (
  echo [osanpo] OSANPO_TOKEN is not set. Create osanpo\windows\osanpo.env first.
  echo [osanpo] Example line:  OSANPO_TOKEN=some-long-random-letters-and-digits
  pause
  exit /b 1
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set OSANPO_LOG=%~dp0osanpo.log
echo [osanpo] start %date% %time% >> "%OSANPO_LOG%"
python -u server.py
