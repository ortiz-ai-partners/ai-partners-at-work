# お散歩Claude: ログオン時に start-osanpo.bat を自動起動するタスクを登録する（Windows 11）
# 使い方: PowerShell を開いて
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\install-autostart.ps1
# 解除:   Unregister-ScheduledTask -TaskName "OsanpoClaude" -Confirm:$false

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat  = Join-Path $here 'start-osanpo.bat'

if (-not (Test-Path (Join-Path $here 'osanpo.env'))) {
  Write-Host "osanpo.env がありません。osanpo.env.example をコピーして合言葉を書いてください。" -ForegroundColor Yellow
  exit 1
}

$action   = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$bat`"" -WorkingDirectory $here
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
Register-ScheduledTask -TaskName 'OsanpoClaude' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "登録しました。次回ログオンから自動起動します。今すぐ試すなら:" -ForegroundColor Green
Write-Host "  Start-ScheduledTask -TaskName OsanpoClaude"
Write-Host "ログ: $here\osanpo.log"
