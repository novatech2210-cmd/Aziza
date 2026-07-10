#!/bin/bash
export LC_ALL=C
apt-get update
apt-get install -y redis-server curl tmux python3-pip python3-venv npm

# Setup node for frontend
cd /root/frontend
npm install
npm install -g vite
# Update vite.config.js to run on port 8080
sed -i '/server: {/a \    port: 8080,\n    host: "0.0.0.0",' vite.config.js

# Setup python backend
cd /root/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -U pydantic fastapi uvicorn redis peft accelerate safetensors

# Start redis
systemctl start redis-server || redis-server --daemonize yes

# Start PersonaPlex
cd /root/backend/persona-plex
tmux new-session -d -s personaplex 'python3 main.py'

# Start Serve Multilingual
cd /root
tmux new-session -d -s serve_multi 'python3 serve_multilingual.py --port 3000'

# Start Frontend
cd /root/frontend
tmux new-session -d -s frontend 'npm run dev'

echo "All services started."
tmux ls
