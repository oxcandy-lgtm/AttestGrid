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
    # Sakura shared servers often have multiple python versions in /usr/local/bin.
    PYTHON_CMD="python3"
    for cmd in "/usr/local/bin/python3.11" "/usr/local/bin/python3.10" "/usr/local/bin/python3.9" python3.11 python3.10 python3.9 python3; do
        if [ -x "$cmd" ] || command -v "$cmd" >/dev/null 2>&1; then
            PYTHON_CMD="$cmd"
            # Ensure it actually works
            if $PYTHON_CMD --version >/dev/null 2>&1; then
                break
            fi
        fi
    done
    
    PY_VER=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "📌 Using Python command: $PYTHON_CMD (Python $PY_VER)"
    
    # Force fresh venv to avoid dependency mix-ups
    echo "🧹 Cleaning old virtual environment..."
    rm -rf .venv
    
    echo "📦 Creating fresh virtual environment using $PYTHON_CMD..."
    $PYTHON_CMD -m venv .venv

    echo "⚙️  Upgrading base tools (pip)..."
    .venv/bin/pip install --upgrade pip

    echo "⚙️  Installing core dependencies from requirements.txt..."
    .venv/bin/pip install --no-cache-dir -r requirements.txt

    echo "⚙️  Attempting to install optional cryptography for performance..."
    # This might fail on shared servers, which is OK because we have the fallback.
    .venv/bin/pip install --no-cache-dir -r requirements-crypto.txt || echo "⚠️  Could not install cryptography. Using pure-Python fallback."

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
