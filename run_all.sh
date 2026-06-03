#!/bin/bash
cd /Users/apple/Downloads/rebusinessautomationproject

# Start Xvfb
pkill Xvfb 2>/dev/null
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
sleep 2

# Start AI monitor agent
nohup python3 ai_monitor_agent/agent.py > dashboard/logs/agent_daemon.log 2>&1 &
echo "Monitor Agent PID: $!"

# Run initial submission
python3 ai_monitor_agent/full_auto_submitter.py

echo "All services started."