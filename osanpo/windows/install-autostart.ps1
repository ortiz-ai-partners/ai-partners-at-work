# osanpo claude: register a logon task that runs start-osanpo.bat (Windows 11)
# Usage (PowerShell):
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#   .\install-autostart.ps1
# Remove: Unregister-ScheduledTask -TaskName "OsanpoClaude" -Confirm:$false
# Keep this file ASCII-only: Windows PowerShell 5.1 reads BOM-less files in the legacy code page.

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat  = Join-Path $here 'start-osanpo.bat'

if (-not (Test-Path (Join-Path $here 'osanpo.env'))) {
  Write-Host "osanpo.env not found. Copy osanpo.env.example to osanpo.env and set OSANPO_TOKEN." -ForegroundColor Yellow
  exit 1
}

$action   = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$bat`"" -WorkingDirectory $here
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
Register-ScheduledTask -TaskName 'OsanpoClaude' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Registered. Starts automatically at next logon. To try now:" -ForegroundColor Green
Write-Host "  Start-ScheduledTask -TaskName OsanpoClaude"
Write-Host "Log: $here\osanpo.log"
