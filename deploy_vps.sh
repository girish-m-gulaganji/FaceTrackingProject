#!/bin/bash
# VisionTrack AI - Automated Linux VPS Deployment Script
# Works on Ubuntu 20.04 / 22.04 / 24.04 and Debian 11 / 12

echo "========================================================"
echo "   VisionTrack AI - Linux VPS Deployment Installer"
echo "========================================================"

# 1. Update system packages & install OpenCV dependencies
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv git curl libgl1-mesa-glx libglib2.0-0 nginx certbot python3-certbot-nginx

# 2. Clone repository if not present
APP_DIR="/var/www/FaceTrackingProject"
if [ ! -d "$APP_DIR" ]; then
    echo "[INFO] Cloning repository..."
    sudo git clone https://github.com/girish-m-gulaganji/FaceTrackingProject.git $APP_DIR
else
    echo "[INFO] Repository exists, pulling latest code..."
    cd $APP_DIR && sudo git pull origin main
fi

# 3. Set directory permissions
sudo chown -R $USER:$USER $APP_DIR
cd $APP_DIR

# 4. Create virtual environment & install dependencies
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Create Systemd Background Service
echo "[INFO] Setting up Systemd Service..."
sudo bash -c 'cat <<EOF > /etc/systemd/system/visiontrack.service
[Unit]
Description=VisionTrack AI FastAPI Server
After=network.target

[Service]
User='$USER'
WorkingDirectory='$APP_DIR'
ExecStart='$APP_DIR'/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF'

# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable visiontrack
sudo systemctl restart visiontrack

# 6. Configure Nginx Reverse Proxy
echo "[INFO] Setting up Nginx Reverse Proxy..."
sudo bash -c 'cat <<EOF > /etc/nginx/sites-available/visiontrack
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF'

sudo ln -sf /etc/nginx/sites-available/visiontrack /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl restart nginx

echo "========================================================"
echo "   ✅ Deployment Complete!"
echo "   Access your Web Dashboard at: http://$(curl -s ifconfig.me)"
echo "========================================================"
