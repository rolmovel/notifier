#!/usr/bin/env bash
# Build script for WhatsApp Notifier
# Produces a distributable package with the Python app and Node.js bridge.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== WhatsApp Notifier Build Script ==="
echo ""

# --- 1. Install Python dependencies ---
echo "[1/5] Installing Python dependencies..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller -q
echo "    ✓ Python dependencies installed"

# --- 2. Install Node.js bridge dependencies ---
echo "[2/5] Installing bridge dependencies..."
if [ -f "bridge/package.json" ]; then
    cd bridge
    if command -v npm &>/dev/null; then
        npm install --production
    elif command -v yarn &>/dev/null; then
        yarn install --production
    else
        echo "    ⚠ npm/yarn not found — bridge dependencies not installed"
        echo "    Install Node.js and run: cd bridge && npm install"
    fi
    cd "$PROJECT_ROOT"
    echo "    ✓ Bridge dependencies installed"
else
    echo "    ⚠ bridge/package.json not found — skipping"
fi

# --- 3. Run tests (optional) ---
echo "[3/5] Running tests..."
if python -m pytest --tb=short -q 2>/dev/null; then
    echo "    ✓ Tests passed"
else
    echo "    ⚠ Tests failed or no tests found — continuing build"
fi

# --- 4. Build Python executable with PyInstaller ---
echo "[4/5] Building Python executable..."
pyinstaller whatsapp-notifier.spec --noconfirm --clean
echo "    ✓ Python executable built: dist/WhatsAppNotifier/"

# --- 5. Assemble distribution ---
echo "[5/5] Assembling distribution package..."
DIST_DIR="dist/WhatsAppNotifier-$(date +%Y%m%d)"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# Copy the PyInstaller output
cp -r dist/WhatsAppNotifier/* "$DIST_DIR/"

# Ensure bridge node_modules are included
if [ -d "bridge/node_modules" ]; then
    mkdir -p "$DIST_DIR/bridge"
    cp -r bridge/node_modules "$DIST_DIR/bridge/"
    cp bridge/package.json "$DIST_DIR/bridge/"
    cp bridge/whatsapp-bridge.js "$DIST_DIR/bridge/"
fi

# Create a README for the distribution
cat > "$DIST_DIR/README.txt" << 'README'
WhatsApp Notifier — Distribution Package
========================================

Requirements:
- Node.js 18+ must be installed on the target machine (for the WhatsApp bridge)

To run:
1. Extract this folder
2. Run WhatsAppNotifier (or WhatsAppNotifier.exe on Windows)

The app will start the WhatsApp bridge automatically.
README

echo ""
echo "=== Build Complete ==="
echo "Distribution: $DIST_DIR"
echo ""
echo "Note: Node.js 18+ must be installed on the target machine."
