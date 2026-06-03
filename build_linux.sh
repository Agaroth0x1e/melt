#!/bin/bash
set -e
echo ""
echo "=== MelT Linux Build Script ==="
echo ""

echo "[1/6] Installing Python dependencies..."
pip3 install -r requirements.txt
pip3 install pyinstaller

echo "[2/6] Generating icon..."
pip3 install pillow -q 2>/dev/null || true
python3 generate_icon.py 2>/dev/null || echo "  Icon generation skipped (pillow not available)"

echo "[3/6] Locating ffmpeg..."
FFMPEG_ARG=""
if command -v ffmpeg &> /dev/null; then
    FFMPEG_PATH=$(which ffmpeg)
    cp "$FFMPEG_PATH" "bin/linux/ffmpeg"
    FFMPEG_ARG="--add-data bin/linux/ffmpeg:."
    echo "  ffmpeg found at $FFMPEG_PATH"
else
    echo "  ffmpeg not found. Downloading static build..."
    mkdir -p "bin/linux"
    wget -q "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" -O "ffmpeg.tar.xz"
    tar -xf "ffmpeg.tar.xz" --strip=1 -C "bin/linux" '*/ffmpeg'
    rm -f "ffmpeg.tar.xz"
    if [ -f "bin/linux/ffmpeg" ]; then
        FFMPEG_ARG="--add-data bin/linux/ffmpeg:."
        echo "  ffmpeg downloaded and bundled"
    else
        echo "  WARNING: ffmpeg download failed — exe will require system ffmpeg"
    fi
fi

echo "[4/6] Building executable..."
ICON=""
if [ -f "bin/windows/icon.ico" ]; then
    ICON="--icon bin/windows/icon.ico"
fi
# Note: .ico works on Linux PyInstaller; for a native PNG icon, use --icon with a .png
SOUNDS_ARG="--add-data sounds:sounds"
if [ -n "$FFMPEG_ARG" ]; then
    pyinstaller --onefile --console --name "melt" \
        $ICON \
        --add-data "config/config.json:config" \
        $FFMPEG_ARG \
        $SOUNDS_ARG \
        main.py
else
    pyinstaller --onefile --console --name "melt" \
        $ICON \
        --add-data "config/config.json:config" \
        $SOUNDS_ARG \
        main.py
fi

echo "[5/6] Copying to bin/linux/ and bin/host/..."
mkdir -p "bin/linux" "bin/host"
cp "dist/melt" "bin/linux/melt"
cp "dist/melt" "bin/host/melt"

echo "[6/6] Cleaning up..."
rm -rf build dist melt.spec bin/linux/ffmpeg

echo ""
echo "=== BUILD COMPLETE ==="
echo "Output: bin/linux/melt"
if [ -n "$FFMPEG_ARG" ]; then
    echo "ffmpeg BUNDLED — no system install needed"
else
    echo "NOTE: ffmpeg NOT bundled — install: sudo apt install ffmpeg"
fi
echo ""
