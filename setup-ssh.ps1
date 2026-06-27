# Setup OpenSSH Server for Remote Access
# Run this script as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OpenSSH Server Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/5] Installing OpenSSH Server..." -ForegroundColor Green
try {
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
    Write-Host "      OpenSSH Server installed successfully!" -ForegroundColor Green
} catch {
    Write-Host "      Warning: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[2/5] Starting SSH service..." -ForegroundColor Green
Start-Service sshd

Write-Host ""
Write-Host "[3/5] Setting SSH service to auto-start..." -ForegroundColor Green
Set-Service -Name sshd -StartupType 'Automatic'

Write-Host ""
Write-Host "[4/5] Configuring firewall rule..." -ForegroundColor Green
if (!(Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
    Write-Host "      Firewall rule created!" -ForegroundColor Green
} else {
    Write-Host "      Firewall rule already exists" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[5/5] Verifying installation..." -ForegroundColor Green
$service = Get-Service -Name sshd
Write-Host "      SSH Service Status: $($service.Status)" -ForegroundColor Cyan
Write-Host "      SSH Service Startup: $($service.StartType)" -ForegroundColor Cyan

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  SSH Server Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Connection Details:" -ForegroundColor Cyan
Write-Host "  Username: $env:USERNAME" -ForegroundColor White
Write-Host "  Port: 22" -ForegroundColor White
Write-Host ""
Write-Host "To connect remotely, use:" -ForegroundColor Cyan
Write-Host "  ssh $env:USERNAME@<your-laptop-ip>" -ForegroundColor Yellow
Write-Host ""
Write-Host "To restart the app remotely:" -ForegroundColor Cyan
Write-Host "  ssh $env:USERNAME@<ip> `"cd Desktop\Freelancer\flipkart-screen; .\start-app-ngrok.ps1`"" -ForegroundColor Yellow
Write-Host ""
