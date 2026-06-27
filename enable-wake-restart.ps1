# Enable wake-from-sleep for FlipkartAppRestart task

$taskName = "FlipkartAppRestart"

Write-Host "Enabling wake-from-sleep for $taskName..." -ForegroundColor Cyan

# Get the task
$task = Get-ScheduledTask -TaskName $taskName

# Update settings to wake computer from sleep
$task.Settings.WakeToRun = $true

# Save changes
$task | Set-ScheduledTask

Write-Host "`n✓ Task updated successfully!" -ForegroundColor Green
Write-Host "`nCurrent settings:" -ForegroundColor Yellow
(Get-ScheduledTask -TaskName $taskName).Settings | Select-Object WakeToRun, AllowStartIfOnBatteries, DontStopIfGoingOnBatteries, RunOnlyIfNetworkAvailable | Format-List

Write-Host "`n✓ Your laptop will now wake from sleep to restart the app every 2 hours!" -ForegroundColor Green
Write-Host "Press any key to close..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
