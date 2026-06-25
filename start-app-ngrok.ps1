# Kill anything on port 8000
Write-Host "Stopping processes on port 8000..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

# Kill orphaned Chrome/ChromeDriver processes from previous runs
Write-Host "Cleaning up orphaned Chrome processes..." -ForegroundColor Yellow
Get-Process -Name chrome, chromedriver -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

# Kill any existing ngrok processes
Write-Host "Stopping existing ngrok processes..." -ForegroundColor Yellow
Get-Process -Name ngrok -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

# Set script directory as app directory
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Write-Host "App directory: $appDir" -ForegroundColor Cyan

# Start ngrok in separate PowerShell window (detached)
Write-Host "Starting ngrok tunnel..." -ForegroundColor Green
$ngrokProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "ngrok http 8000" -WindowStyle Normal -PassThru

# Wait for ngrok to initialize
Start-Sleep -Seconds 3

# Verify ngrok started
if (Get-Process -Id $ngrokProcess.Id -ErrorAction SilentlyContinue) {
    Write-Host "✓ ngrok started (PID: $($ngrokProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "⚠ Warning: ngrok may not have started" -ForegroundColor Yellow
}

# Start uvicorn in current terminal (blocking - shows logs here)
Write-Host "Starting uvicorn on port 8000..." -ForegroundColor Green
$venvActivate = Join-Path $appDir ".venv\bin\Activate.ps1"
cd $appDir
& $venvActivate
uvicorn app:app --host 0.0.0.0 --port 8000
