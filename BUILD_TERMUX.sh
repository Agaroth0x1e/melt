#!/data/data/com.termux/files/usr/bin/bash
# =====================================================
# Setup YT-DL for Termux (Android)
# Run this script INSIDE Termux terminal
# =====================================================
echo ""
echo "=== MelT Termux Setup ==="
echo ""

echo "[1/4] Updating Termux packages..."
pkg update -y && pkg upgrade -y

echo "[2/4] Installing Python and ffmpeg..."
pkg install -y python ffmpeg

echo "[3/4] Installing Python packages..."
pip install -r requirements.txt || {
    echo "FAILED: pip install"
    exit 1
}

echo "[4/4] Creating launcher..."
mkdir -p $PREFIX/bin
cat > $PREFIX/bin/melt << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$(readlink -f "$0")")/.."
python main.py "$@"
EOF
chmod +x $PREFIX/bin/melt

echo ""
echo "=== SETUP COMPLETE ==="
echo ""
echo "Run: melt"
echo "Or:  python main.py"
echo ""
echo "NOTE: ffmpeg is already installed."
echo ""
