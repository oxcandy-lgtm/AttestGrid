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
    # Try to find a modern one (3.9 - 3.12). Some use dots, some don't.
    PYTHON_CMD="python3"
    for cmd in python3.12 python3.11 python3.10 python3.9 python311 python310 python39; do
        if command -v "$cmd" >/dev/null 2>&1; then
            PYTHON_CMD="$cmd"
            break
        fi
    done
    
    PY_VER=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "📌 Using Python command: $PYTHON_CMD (Python $PY_VER)"
    
    if [ ! -d ".venv" ]; then
        echo "📦 Creating virtual environment using $PYTHON_CMD..."
        $PYTHON_CMD -m venv .venv
    fi

    echo "⚙️  Upgrading base tools (pip, setuptools, wheel)..."
    .venv/bin/pip install --upgrade pip setuptools wheel

    echo "⚙️  Installing dependencies..."
    # If Python is < 3.9, we need to pin cryptography to a version that supports it.
    # Also using --prefer-binary to avoid building from source on shared hosts.
    if [[ "$PY_VER" == "3.8" ]]; then
        echo "⚠️  Old Python detected. Pinning cryptography<44.0.0"
        .venv/bin/pip install --prefer-binary "cryptography<44.0.0" fastapi uvicorn pydantic
    else
        .venv/bin/pip install --prefer-binary cryptography fastapi uvicorn pydantic
    fi

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
