#!/bin/bash

echo "========================================================"
echo "   ThomasNet Automation - Proxy Configuration Setup"
echo "========================================================"
echo "This automation requires a Residential Proxy to bypass DataDome."
echo "You must obtain credentials from a provider like:"
echo " - Bright Data"
echo " - Smartproxy"
echo " - IPRoyal"
echo " - Webshare"
echo "========================================================"

# Prompt for details
read -p "Enter Proxy Host (e.g., pr.oxylabs.io): " HOST
read -p "Enter Proxy Port (e.g., 7777): " PORT
read -p "Enter Username: " USER
read -s -p "Enter Password: " PASS
echo ""

if [ -z "$HOST" ] || [ -z "$PORT" ]; then
    echo "❌ Error: Host and Port are required."
    exit 1
fi

# Construct URL
# If username is provided, format: http://user:pass@host:port
if [ -n "$USER" ]; then
    PROXY_URL="http://$USER:$PASS@$HOST:$PORT"
else
    PROXY_URL="http://$HOST:$PORT"
fi

# URL Encode special characters in password if needed? 
# For simplicity, we assume standard chars or user enters encoded.

# Update .env
ENV_FILE="dashboard/.env"
if [ ! -f "$ENV_FILE" ]; then
    touch "$ENV_FILE"
fi

# Remove existing proxy lines
sed -i.bak '/THOMASNET_PROXY_/d' "$ENV_FILE"

# Add new configuration
echo "THOMASNET_PROXY_SERVER=$PROXY_URL" >> "$ENV_FILE"
echo "THOMASNET_PROXY_USERNAME=$USER" >> "$ENV_FILE"
echo "THOMASNET_PROXY_PASSWORD=$PASS" >> "$ENV_FILE"

echo "✅ Configuration saved to $ENV_FILE"
echo "========================================================"
echo "To apply changes, restart the server:"
echo "bash dashboard/start_server.sh 5001 --bg"
echo "========================================================"
