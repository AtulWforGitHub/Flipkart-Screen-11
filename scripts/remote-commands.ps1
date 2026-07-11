# Remote App Restart Commands via SSH
# Use these commands from another computer

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Remote Access Commands" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get local IP
$ipAddress = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress

Write-Host "Your laptop IP address: $ipAddress" -ForegroundColor Green
Write-Host "Username: $env:USERNAME" -ForegroundColor Green
Write-Host ""

Write-Host "COMMANDS TO USE FROM REMOTE COMPUTER:" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. Connect to SSH:" -ForegroundColor Yellow
Write-Host "   ssh $env:USERNAME@$ipAddress" -ForegroundColor White
Write-Host ""

Write-Host "2. Restart the app (one command):" -ForegroundColor Yellow
$restartCmd = "ssh $env:USERNAME@$ipAddress `"cd Desktop\Freelancer\flipkart-screen; & '.\start-app-ngrok.ps1'`""
Write-Host "   $restartCmd" -ForegroundColor White
Write-Host ""

Write-Host "3. Check if app is running:" -ForegroundColor Yellow
$checkCmd = "ssh $env:USERNAME@$ipAddress `"Get-Process -Name python -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime`""
Write-Host "   $checkCmd" -ForegroundColor White
Write-Host ""

Write-Host "4. Kill port 8000 (if stuck):" -ForegroundColor Yellow
$killCmd = "ssh $env:USERNAME@$ipAddress `"Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id `$_.OwningProcess -Force }`""
Write-Host "   $killCmd" -ForegroundColor White
Write-Host ""

Write-Host "SAVE THESE COMMANDS!" -ForegroundColor Green
Write-Host "Copy them to your phone or another computer for remote access." -ForegroundColor Yellow
Write-Host ""
