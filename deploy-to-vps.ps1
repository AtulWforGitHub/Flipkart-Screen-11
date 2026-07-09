# Simple VPS Deployment Script
$VPS = "root@187.127.191.228"

Write-Host "=== Flipkart App - VPS Deployment ===" -ForegroundColor Cyan

# Step 1: Create directory
Write-Host "`nStep 1: Creating directory on VPS..." -ForegroundColor Yellow
ssh $VPS "mkdir -p ~/flipkart-app"

# Step 2: Upload all files
Write-Host "Step 2: Uploading files..." -ForegroundColor Yellow
scp app.py flipkart_scraper.py flipkart_login.py config.py dashboard.html requirements.txt Dockerfile client_cookies.json client_cookies_backup.json vps-setup.sh "${VPS}:~/flipkart-app/"
Write-Host "  Files uploaded" -ForegroundColor Green

# Step 3: Run setup script
Write-Host "`nStep 3: Running setup on VPS (this may take 2-3 minutes)..." -ForegroundColor Yellow
ssh $VPS 'cd ~/flipkart-app; chmod +x vps-setup.sh; ./vps-setup.sh'

Write-Host "`n=== Deployment Complete! ===" -ForegroundColor Green
Write-Host "Dashboard: http://187.127.191.228:8000" -ForegroundColor Cyan
