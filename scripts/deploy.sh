#!/bin/bash
set -e

# Configuration (Edit these or pass as env vars)
REMOTE_HOST="${REMOTE_HOST:-gemini}" # User defined helper or user@ip
REMOTE_DIR="${REMOTE_DIR:-/home/start/dynamic-blazar}" # Default path on server
SERVICE_PORT="${SERVICE_PORT:-8000}"

echo "🚀 Deploying to $REMOTE_HOST:$REMOTE_DIR..."

ssh "$REMOTE_HOST" "bash -s" -- "$REMOTE_DIR" "$SERVICE_PORT" << 'EOF'
    REMOTE_DIR="$1"
    SERVICE_PORT="$2"
    set -e
    echo "📂 Navigating to $REMOTE_DIR..."
    cd "$REMOTE_DIR"

    echo "📥 Pulling latest code..."
    git pull origin main --tags

    echo "🔍 Checking environment..."
    # Sakura shared servers often have multiple python versions. 
    # Try to find a modern one (3.10 or 3.11+)
    PYTHON_CMD="python3"
    for cmd in python3.11 python3.10 python3.9; do
        if command -v "$cmd" >/dev/null 2>&1; then
            PYTHON_CMD="$cmd"
            break
        fi
    done
    
    echo "📌 Using Python command: $PYTHON_CMD ($($PYTHON_CMD --version))"
    
    if [ ! -d ".venv" ]; then
        echo "📦 Creating virtual environment using $PYTHON_CMD..."
        $PYTHON_CMD -m venv .venv
    fi

    echo "⚙️  Upgrading base tools (pip, setuptools, wheel)..."
    .venv/bin/pip install --upgrade pip setuptools wheel

    echo "⚙️  Installing dependencies..."
    .venv/bin/pip install cryptography fastapi uvicorn pydantic

    echo "🔄 Restarting application..."
    # Kill existing uvicorn process if running, ignore error if not found
    pkill -f uvicorn || true
    
    # Wait a moment
    sleep 2

    # Start new process in background
    # Adjust python path if using venv differently (e.g. .venv/bin/uvicorn)
    # Using nohup to keep it running after disconnect
    nohup .venv/bin/uvicorn src.attestation.server:app --host 0.0.0.0 --port $SERVICE_PORT > server.log 2>&1 &
    
    echo "✅ Deployment trigger complete. Checking status..."
    sleep 2
    ps aux | grep uvicorn | grep -v grep
EOF

echo "🎉 Deployment command sent successfully!"
