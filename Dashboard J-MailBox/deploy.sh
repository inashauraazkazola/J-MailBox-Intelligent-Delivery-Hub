#!/bin/bash
# deploy.sh - Deployment script for J-MailBox on VPS

echo "🚀 Deploying J-MailBox Control Center..."

# Update system
sudo apt update
sudo apt upgrade -y

# Install Python and required packages
sudo apt install -y python3 python3-pip python3-venv nginx

# Create project directory
mkdir -p /var/www/jmailbox
cd /var/www/jmailbox

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install streamlit pandas numpy plotly paho-mqtt requests Werkzeug

# Create database and initialize
python3 -c "
from database import DatabaseManager
db = DatabaseManager()
print('✅ Database initialized')
"

# Create systemd service for Streamlit
sudo tee /etc/systemd/system/jmailbox.service > /dev/null <<EOF
[Unit]
Description=J-MailBox Control Center
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/jmailbox
Environment="PATH=/var/www/jmailbox/venv/bin"
ExecStart=/var/www/jmailbox/venv/bin/streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx as reverse proxy
sudo tee /etc/nginx/sites-available/jmailbox > /dev/null <<EOF
server {
    listen 80;
    server_name your-domain.com;  # Ganti dengan domain Anda

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /api {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/jmailbox /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Enable and start Streamlit service
sudo systemctl daemon-reload
sudo systemctl enable jmailbox
sudo systemctl start jmailbox

# Start Flask API server (jika diperlukan)
sudo tee /etc/systemd/system/jmailbox-api.service > /dev/null <<EOF
[Unit]
Description=J-MailBox API Server
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/jmailbox
Environment="PATH=/var/www/jmailbox/venv/bin"
ExecStart=/var/www/jmailbox/venv/bin/python receiver_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable jmailbox-api
sudo systemctl start jmailbox-api

echo "✅ Deployment complete!"
echo "🌐 Access your dashboard at: http://your-domain.com"
echo "📊 Streamlit running on: http://localhost:8501"
echo "🔧 Check status: sudo systemctl status jmailbox"