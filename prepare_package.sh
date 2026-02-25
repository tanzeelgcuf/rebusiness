#!/bin/bash

# Package application for deployment
echo "📦 Packaging application for deployment..."

# Create exclusion list
cat <<EOF > .deployignore
venv/
__pycache__/
*.pyc
.git/
.DS_Store
rfq_downloads/
*.zip
dashboard/rfq_downloads/
EOF

# Create zip file
zip -r rfq_automation_deploy.zip . -x@.deployignore

echo "✅ Package created: rfq_automation_deploy.zip"
echo "Instructions:"
echo "1. SCP this file to your server: scp rfq_automation_deploy.zip ubuntu@SERVER_IP:~/"
echo "2. SSH into server"
echo "3. Unzip: unzip rfq_automation_deploy.zip -d rfq-automation"
echo "4. Run: cd rfq-automation && sudo bash deploy_server.sh"
