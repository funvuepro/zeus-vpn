$ErrorActionPreference = 'Continue'
$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location $projectDir

$logFile = Join-Path $projectDir 'bot_run.log'

while ($true) {
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $logFile -Value "=== [$timestamp] watchdog: starting bot ===" -Encoding utf8

    cmd /c "python -m bot.main >> `"$logFile`" 2>&1"

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $logFile -Value "=== [$timestamp] watchdog: bot exited (code $LASTEXITCODE), restarting in 5s ===" -Encoding utf8
    Start-Sleep -Seconds 5
}
