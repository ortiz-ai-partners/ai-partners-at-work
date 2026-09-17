@echo off
setlocal
REM stackchan-mcp gateway (persistent, streamable-http on 127.0.0.1:8767)
REM Reads STACKCHAN_TOKEN / VISION_HOST from osanpo\windows\osanpo.env. ASCII-only file.

chcp 65001 >nul
pushd "%~dp0.."

if exist "%~dp0osanpo.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0osanpo.env") do set "%%A=%%B"
)

if "%STACKCHAN_TOKEN%"=="" (
  echo [gateway] STACKCHAN_TOKEN is not set in osanpo\windows\osanpo.env
  pause
  exit /b 1
)
if "%VISION_HOST%"=="" (
  echo [gateway] VISION_HOST is not set in osanpo\windows\osanpo.env  (this PC's LAN IP, e.g. 192.168.4.32)
  pause
  exit /b 1
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo [gateway] token set, VISION_HOST=%VISION_HOST%
stackchan-mcp serve --transport streamable-http
popd
