# Create Scheduled Task to Restart App Every 2 Hours
# Run this script as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Auto-Restart Scheduler Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again." -ForegroundColor Yellow
    exit 1
}

$taskName = "FlipkartAppRestart"
$appDir = "c:\Users\Vasu\Desktop\Freelancer\flipkart-screen"
$scriptPath = "$appDir\start-app-ngrok.ps1"

# Remove existing task if it exists
Write-Host "[1/3] Removing old task (if exists)..." -ForegroundColor Green
try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "      Old task removed" -ForegroundColor Yellow
} catch {
    Write-Host "      No old task found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[2/3] Creating scheduled task..." -ForegroundColor Green

# Create action - run PowerShell with the script
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"& '$scriptPath'`""

# Create trigger - every 2 hours, starting now
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 2)

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

# Register the task to run as current user
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Write-Host "      Creating task: $taskName" -ForegroundColor Cyan
Register-ScheduledTask -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Automatically restarts Flipkart price tracker app every 2 hours"

Write-Host ""
Write-Host "[3/3] Verifying task..." -ForegroundColor Green
$task = Get-ScheduledTask -TaskName $taskName
Write-Host "      Task Name: $($task.TaskName)" -ForegroundColor Cyan
Write-Host "      State: $($task.State)" -ForegroundColor Cyan
Write-Host "      Next Run: $(Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo | Select-Object -ExpandProperty NextRunTime)" -ForegroundColor Cyan

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Auto-Restart Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "The app will automatically restart every 2 hours." -ForegroundColor Yellow
Write-Host ""
Write-Host "To view the task:" -ForegroundColor Cyan
Write-Host "  Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor White
Write-Host ""
Write-Host "To disable auto-restart:" -ForegroundColor Cyan
Write-Host "  Disable-ScheduledTask -TaskName '$taskName'" -ForegroundColor White
Write-Host ""
Write-Host "To enable auto-restart:" -ForegroundColor Cyan
Write-Host "  Enable-ScheduledTask -TaskName '$taskName'" -ForegroundColor White
Write-Host ""
Write-Host "To remove auto-restart:" -ForegroundColor Cyan
Write-Host "  Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false" -ForegroundColor White
Write-Host ""
