#!/bin/bash
PORT=${1:-5001}

# Navigate to script directory
cd "$(dirname "$0")"

# Activate Venv (handle relative path from dashboard dir)
if [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "⚠️  Virtual environment not found! Please create one."
fi

# Ensure logs dir exists
mkdir -p logs

echo "========================================================"
echo "  RFQ Management Dashboard"
echo "========================================================"
echo "  Port: $PORT"
echo "========================================================"

# Run
if command -v gunicorn &> /dev/null; then
    echo "🚀 Starting with Gunicorn..."
    if [[ "$2" == "--bg" ]]; then
        pkill -f "gunicorn.*:$PORT"
        nohup gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 300 app:app > logs/gunicorn.log 2>&1 &
        echo "   Running in background. Logs: logs/gunicorn.log"
    else
        gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 300 app:app
    fi
else
    echo "⚠️  Gunicorn not found. Installing..."
    pip install gunicorn
    exec "$0" "$@"
fi
