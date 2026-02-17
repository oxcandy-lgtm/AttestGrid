#!/bin/bash
set -e

# Configuration (Edit these or pass as env vars)
REMOTE_HOST="${REMOTE_HOST:-gemini}" # User defined helper or user@ip
REMOTE_DIR="${REMOTE_DIR:-/home/start/dynamic-blazar}" # Default path on server
SERVICE_PORT="${SERVICE_PORT:-8000}"

echo "🚀 Deploying to $REMOTE_HOST:$REMOTE_DIR..."

ssh "$REMOTE_HOST" "bash -s" << EOF
    set -e
    echo "📂 Navigating to $REMOTE_DIR..."
    cd "$REMOTE_DIR"

    echo "� Checking environment..."
    python3 --version || echo "python3 not found"
    
    if [ ! -d ".venv" ]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv .venv
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
