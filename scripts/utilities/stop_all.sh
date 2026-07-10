#!/bin/bash
killall -9 node
pkill -9 -f "uvicorn main:app"
pkill -9 -f "python3 main.py"
pkill -9 -f "python3 moshi_service.py"
pkill -9 -f "python3 runtime.py"
pkill -9 -f "telephony-bridge/main.py"

echo "All Aziza services stopped!"
