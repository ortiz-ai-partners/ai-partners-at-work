@echo off
REM お散歩Claude 受信サーバ起動（Windows 11）
REM タスクスケジューラからログオン時に呼ばれる。手で叩いてもよい。
REM 合言葉は環境変数 OSANPO_TOKEN に。ここに直書きしないこと（.envから読む）。

cd /d "%~dp0.."

if exist "%~dp0osanpo.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0osanpo.env") do set "%%A=%%B"
)

if "%OSANPO_TOKEN%"=="" (
  echo [osanpo] OSANPO_TOKEN が未設定です。osanpo\windows\osanpo.env を作ってください。
  echo [osanpo] 例:  OSANPO_TOKEN=長いランダムな文字列
  pause
  exit /b 1
)

echo [osanpo] start %date% %time% >> "%~dp0osanpo.log"
python server.py >> "%~dp0osanpo.log" 2>&1
