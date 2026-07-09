#!/bin/bash
# VPS Setup Script - Run this on your Hostinger VPS

set -e

echo "=== Flipkart App - VPS Setup ==="

# Update system
echo "[1/5] Updating system..."
apt update
apt install -y python3 python3-pip python3-venv wget curl

# Install Chrome
echo "[2/5] Installing Chrome..."
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt install -y ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb

# Setup app directory
echo "[3/5] Setting up app..."
cd ~/flipkart-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create systemd service
echo "[4/5] Creating service..."
cat > /etc/systemd/system/flipkart.service <<'EOF'
[Unit]
Description=Flipkart Price Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/flipkart-app
Environment=PATH=/root/flipkart-app/venv/bin
ExecStart=/root/flipkart-app/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Start service
echo "[5/5] Starting service..."
systemctl daemon-reload
systemctl enable flipkart
systemctl start flipkart

echo ""
echo "✓ Setup complete!"
echo "App is running at: http://$(curl -s ifconfig.me):8000"
echo ""
echo "Useful commands:"
echo "  View logs:    journalctl -u flipkart -f"
echo "  Restart:      systemctl restart flipkart"
echo "  Stop:         systemctl stop flipkart"
echo "  Status:       systemctl status flipkart"
