#!/bin/bash

# RFQ Automation Dashboard - Deployment Script
# For Ubuntu 22.04 LTS

set -e  # Exit on error

echo "================================================================="
echo "   RFQ Automation Dashboard - Server Setup"
echo "================================================================="

# 1. Update System
echo "[1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git nginx unzip wget curl

# 2. Install Chrome
echo "[2/6] Installing Google Chrome..."
if ! command -v google-chrome &> /dev/null; then
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt install -y ./google-chrome-stable_current_amd64.deb
    rm google-chrome-stable_current_amd64.deb
else
    echo "Chrome already installed."
fi

# 3. Setup Application
echo "[3/6] Setting up application..."
PROJECT_DIR="/home/ubuntu/rfq-automation"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Creating project directory at $PROJECT_DIR"
    mkdir -p "$PROJECT_DIR"
    echo "Please upload your application files to $PROJECT_DIR"
fi

# Setup Python Environment
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

# Install dependencies if requirements.txt exists
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "Installing Python dependencies..."
    "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
    "$PROJECT_DIR/venv/bin/playwright" install
    "$PROJECT_DIR/venv/bin/playwright" install-deps
fi

# 4. Configure Gunicorn Service
echo "[4/6] Configuring Gunicorn service..."
cat <<EOF | sudo tee /etc/systemd/system/rfq-dashboard.service
[Unit]
Description=RFQ Automation Dashboard
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$PROJECT_DIR/dashboard
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5001 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable rfq-dashboard
sudo systemctl restart rfq-dashboard

# 5. Configure Headless Chrome Service
echo "[5/6] Configuring Headless Chrome service..."
cat <<EOF | sudo tee /etc/systemd/system/headless-chrome.service
[Unit]
Description=Headless Chrome for Automation
After=network.target

[Service]
User=ubuntu
ExecStart=/usr/bin/google-chrome --headless --remote-debugging-port=9222 --disable-gpu --no-sandbox --user-data-dir=/tmp/chrome-data
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable headless-chrome
sudo systemctl restart headless-chrome

# 6. Configure Nginx
echo "[6/6] Configuring Nginx reverse proxy..."
cat <<EOF | sudo tee /etc/nginx/sites-available/rfq-dashboard
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/rfq-dashboard /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl restart nginx
sudo ufw allow 'Nginx Full'

echo "================================================================="
echo "   ✅ Deployment Complete!"
echo "   Access your dashboard at: http://$(curl -s ifconfig.me)"
echo "================================================================="
