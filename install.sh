#!/bin/bash
set -e
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo bash -c "cat > /etc/systemd/system/inbody.service << 'SERVEOF'
[Unit]
Description=InBody Progress Tracker
After=network.target

[Service]
User=$USER
Group=$USER
WorkingDirectory=$(pwd)
Environment=\"PATH=$(pwd)/venv/bin\"
ExecStart=$(pwd)/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVEOF"
sudo systemctl daemon-reload
sudo systemctl enable --now inbody.service
echo "Сервис запущен на порту 8000"
