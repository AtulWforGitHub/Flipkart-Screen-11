# Start the watchdog service in a separate PowerShell window
Write-Host "Starting Flipkart App Watchdog Service..." -ForegroundColor Cyan

$appDir = "c:\Users\Vasu\Desktop\Freelancer\flipkart-screen"
$venvPython = "$appDir\.venv\Scripts\python.exe"
$watchdogScript = "$appDir\watchdog\watchdog.py"

Write-Host "Watchdog will monitor: http://localhost:8000/health" -ForegroundColor Yellow
Write-Host "Logs will be written to: watchdog\watchdog.log" -ForegroundColor Yellow
Write-Host ""

# Start watchdog in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$appDir'; & '$venvPython' '$watchdogScript'" -WindowStyle Normal

Write-Host "Watchdog service started in new window" -ForegroundColor Green
Write-Host "The watchdog will automatically restart the app if health checks fail." -ForegroundColor Green
