#!/bin/bash
set -e

echo "1. Starting MongoDB in Docker..."
docker run -d -p 27017:27017 --name mongodb --restart always mongo:latest || docker start mongodb

echo "2. Updating .env ports and configuration..."
sed -i 's/LLM_URL_EN="http:\/\/localhost:8000"/LLM_URL_EN="http:\/\/localhost:8002"/' /root/aziza-build/.env
sed -i 's/LLM_URL_UZ="http:\/\/localhost:8001"/LLM_URL_UZ="http:\/\/localhost:8003"/' /root/aziza-build/.env
# Split VRAM 45% for EN, 45% for UZ (already configured)
sed -i 's/LLM_GPU_EN=0/LLM_GPU_EN=0/' /root/aziza-build/.env
sed -i 's/LLM_GPU_UZ=0/LLM_GPU_UZ=0/' /root/aziza-build/.env

echo "3. Updating Moshi Adapter Paths in PM2 config..."
# We need to load BOTH Russian and Uzbek adapters into moshi-worker.
# Let's set AZIZA_ADAPTER_PATH to a comma-separated list of adapters, or update it if it only supports one.
# Wait, typically we can just point it to the directories. Let's see if we can do that in ecosystem.config.js
sed -i 's|/root/aziza-build/training/lora/moshi_ru_v1/final|/root/aziza/training/lora/ru_all,/root/aziza-build/training/lora/aziza-adapter-final-uz|g' /root/aziza-build/ecosystem.config.js

echo "4. Checking moshi_service.py to see how it expects adapters..."
cat /root/aziza-build/backend/services/moshi-worker/moshi_service.py | grep -i "adapter" -C 2

echo "5. Restarting PM2 services..."
cd /root/aziza-build
pm2 reload all
pm2 save
