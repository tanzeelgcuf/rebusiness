#!/bin/bash

# Package application for deployment
echo "📦 Packaging application for deployment..."

# Create exclusion list
cat <<EOF > .deployignore
venv/*
.venv/*
__pycache__/*
*.pyc
.git/*
.DS_Store
rfq_downloads/*
*.zip
dashboard/rfq_downloads/*
*.log
page_source_*.html
temp_*.html
selenium_profile/*
downloads/*
rfq_outputs/*
dashboard/logs/*
data/*
EOF

# Create zip file
zip -r rfq_automation_deploy.zip . \
  -x "venv/*" \
  -x ".venv/*" \
  -x ".git/*" \
  -x "data/*" \
  -x "downloads/*" \
  -x "rfq_downloads/*" \
  -x "dashboard/rfq_downloads/*" \
  -x "__pycache__/*" \
  -x "*.pyc" \
  -x ".DS_Store" \
  -x "*.log" \
  -x "page_source_*.html" \
  -x "temp_*.html" \
  -x "selenium_profile/*" \
  -x "rfq_outputs/*" \
  -x "dashboard/logs/*" \
  -x "rfq_automation_deploy.zip"

echo "✅ Package created: rfq_automation_deploy.zip"
echo "Instructions:"
echo "1. SCP this file to your server: scp rfq_automation_deploy.zip ubuntu@SERVER_IP:~/"
echo "2. SSH into server"
echo "3. Unzip: unzip rfq_automation_deploy.zip -d rfq-automation"
echo "4. Run: cd rfq-automation && sudo bash deploy_server.sh"
