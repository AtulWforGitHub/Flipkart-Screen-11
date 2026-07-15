$SERVER = "root@187.127.191.228"
$LOCAL = "C:\Users\Vasu\Desktop\Freelancer\flipkart-screen"
$REMOTE = "/root/flipkart-app"

Write-Host "Copying files..." -ForegroundColor Cyan
scp "$LOCAL\app.py" "$LOCAL\dashboard.html" "$LOCAL\flipkart_scraper.py" "$LOCAL\flipkart_login.py" "$LOCAL\config.py" "$LOCAL\cookie_manager.py" "$LOCAL\bank_offers_extractor.py" "$LOCAL\requirements.txt" "${SERVER}:${REMOTE}/"

Write-Host "Restarting app..." -ForegroundColor Cyan
ssh $SERVER "systemctl restart flipkart && sleep 2 && systemctl is-active flipkart"

Write-Host "Deploy done!" -ForegroundColor Green
