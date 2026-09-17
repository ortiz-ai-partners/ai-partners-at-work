@echo off
setlocal
REM osanpo walk loop: asks the gateway for a photo every N minutes and hands it to server.py
REM   start-walk.bat          loop
REM   start-walk.bat --once   one shot (test)

chcp 65001 >nul
pushd "%~dp0.."

if exist "%~dp0osanpo.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0osanpo.env") do set "%%A=%%B"
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python -u walk.py %*
popd
