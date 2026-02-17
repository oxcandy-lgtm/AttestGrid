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
    
    if [ ! -d ".venv" ]; then
        echo "📦 Creating virtual environment using $PYTHON_CMD..."
        $PYTHON_CMD -m venv .venv
    fi

    echo "⚙️  Upgrading base tools (pip, setuptools, wheel)..."
    .venv/bin/pip install --upgrade pip setuptools wheel

    echo "⚙️  Installing dependencies..."
    # Try with --prefer-binary first. If it's an old Python, we might need --only-binary to avoid build hell.
    if [[ "$PY_VER" == "3.8" ]]; then
        echo "⚠️  Old Python detected. Forcing binary-only and legacy compatibility."
        # cryptography 3.4.8 is the last version without Rust requirement for easier fallback, 
        # but let's try to just get a binary wheel for something slightly newer if possible.
        # Pinning pydantic < 2 to avoid pydantic-core build issues on old systems.
        .venv/bin/pip install --only-binary=:all: "cryptography<40.0" "pydantic<2.0" fastapi uvicorn || \
        .venv/bin/pip install --prefer-binary "cryptography<35.0" "pydantic<2.0" fastapi uvicorn
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
