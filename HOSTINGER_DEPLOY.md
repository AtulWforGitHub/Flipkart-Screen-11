# Hostinger Deployment Checklist

## Pre-Deployment Changes ✅
- [x] Set `BROWSER_HEADLESS = True` in config.py
- [x] Set `SELECT_SAVED_ADDRESS = True` in config.py  
- [x] Use environment variables for credentials in app.py

## Files to Upload

### Required Files:
1. **Application Files**
   - `app.py`
   - `config.py`
   - `flipkart_scraper.py`
   - `requirements.txt`
   - `dashboard.html`
   
2. **Cookie File** (IMPORTANT!)
   - `client_cookies.json` (Rahul's 16 cookies)

3. **Start Script**
   - `start-app-ngrok.ps1` (for local) OR create Linux start script

## Hostinger Setup Steps

### 1. Install System Dependencies
```bash
# Update system
sudo apt-get update

# Install Chrome/Chromium
sudo apt-get install -y chromium-browser chromium-chromedriver

# OR install Google Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f
```

### 2. Install Python Dependencies
```bash
python3 -m pip install -r requirements.txt
```

### 3. Set Environment Variables
Create `/etc/environment` or use `.env` file:
```bash
export MONGO_URI="mongodb+srv://vasu4651_db_user:8Jgyc1ZaTDw5Y5cn@cluster0.rt55a2o.mongodb.net/?appName=Cluster0"
export TELEGRAM_TOKEN="8953384321:AAGwWwD-7fkcR7hIMYrIxm-m8wZfXpKbKAs"
export TELEGRAM_CHAT_ID="1124426595"
```

### 4. Upload Cookie File
- Upload `client_cookies.json` to the same directory as `app.py`
- Verify it contains 16 cookies for Rahul's account

### 5. Create Systemd Service (Linux)
Create `/etc/systemd/system/flipkart-monitor.service`:
```ini
[Unit]
Description=Flipkart Price Monitor
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/flipkart-screen
Environment="PATH=/usr/bin:/usr/local/bin"
EnvironmentFile=/path/to/.env
ExecStart=/usr/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable flipkart-monitor
sudo systemctl start flipkart-monitor
sudo systemctl status flipkart-monitor
```

### 6. Configure Firewall
```bash
sudo ufw allow 8000/tcp
```

### 7. Test Deployment
```bash
curl http://localhost:8000/health
```

## Important Notes

### Browser in Headless Mode
- Chrome/Chromium must be installed on server
- Chromedriver must match Chrome version
- Headless mode doesn't require X11/display

### Cookie Management
- Cookies loaded from `client_cookies.json`
- Account: Rahul (16 cookies)
- Location: Gurugram (HOME address)

### Address Selection Feature
- Enabled by default (`SELECT_SAVED_ADDRESS = True`)
- Waits 3 seconds for delivery section to load
- Logs address name in each product line
- Format: `[Rahul] - [Home]` or `[Rahul] - [Home - H N]`

### Logs
- App logs: Check systemd journal `journalctl -u flipkart-monitor -f`
- Activity logs: Check `activity.log` file

## Troubleshooting

### Chrome Not Found
```bash
which chromium-browser
which google-chrome
# Update path in code if needed
