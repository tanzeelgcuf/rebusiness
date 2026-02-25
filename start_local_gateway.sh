#!/bin/bash

echo "🚀 Setting up Local Proxy Gateway..."

# 1. Start custom SOCKS5 proxy on localhost:1080
echo "Starting local Python SOCKS5 server on port 1080..."
python3 socks_server.py 1080 &
PROXY_PID=$!

# Give it a second to start
sleep 2

echo "✅ Proxy running locally on Port 1080 (PID $PROXY_PID)"
echo "📡 Establishing Reverse SSH Tunnel to Cloud VM..."
echo "   (Cloud Port 9999 -> Local Port 1080)"
echo "   Keep this terminal OPEN while the automation runs!"

# 2. Connect to Cloud VM with Reverse Forwarding (-R)
# Format: -R remote_port:target_host:target_port
gcloud compute ssh --zone "us-central1-a" "rfq-dashboard" --project "samgov-478418" -- -R 9999:127.0.0.1:1080 -N

# Cleanup when SSH exits
echo "Stopping local proxy..."
kill $PROXY_PID
