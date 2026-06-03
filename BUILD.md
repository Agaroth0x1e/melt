# Building MelT from Source

## Prerequisites (all platforms)

| Dependency | Install | Required |
|------------|---------|----------|
| **Python 3.8+** | [python.org](https://python.org) | Yes |
| **ffmpeg** | See platform below | Yes |
| **Pillow** | `pip install pillow` | Only for icon generation |
| **Node.js** | [nodejs.org](https://nodejs.org) | 2x yt-dlp speed |

---

## Windows

### Pre-built .exe (recommended)
Download from [Releases](https://github.com/Agaroth0x1e/melt/releases) — `melt.exe`, fully standalone, ffmpeg bundled.

### Build from source (auto-bundles ffmpeg)
```batch
.\BUILD_WINDOWS.bat
```
Output: `dist\melt.exe` — fully standalone with bundled ffmpeg.

### Run from source (no build)
```batch
pip install -r requirements.txt
python main.py
```
Requires ffmpeg in PATH (`scoop install ffmpeg`)

---

## macOS

### Run from source
```bash
pip3 install -r requirements.txt
python3 main.py
```

### Build portable binary (ffmpeg auto-bundled)
```bash
chmod +x build_macos.sh
./build_macos.sh
```
Output: `dist/melt` — fully standalone if ffmpeg was bundled.

---

## Linux

### Run from source
```bash
pip3 install -r requirements.txt
python3 main.py
```

### Build portable binary (ffmpeg auto-bundled)
```bash
chmod +x build_linux.sh
./build_linux.sh
```
Output: `dist/melt` — fully standalone if ffmpeg was bundled.

---

## Termux (Android)

Step-by-step setup from a fresh Termux install.

### 1. Install Termux

- **F-Droid (recommended):** Install from [F-Droid](https://f-droid.org/packages/com.termux/) (Play Store version is outdated)
- Also install **Termux:API** from F-Droid (enables sound notifications)

### 2. Open Termux and grant storage access

```bash
termux-setup-storage
# Allow the permission popup
```

### 3. Update packages

```bash
pkg update -y && pkg upgrade -y
```

### 4. Install dependencies

```bash
pkg install -y python ffmpeg nodejs
```

### 5. Install Termux:API package

```bash
pkg install -y termux-api
```

### 6. Copy MelT to your device

```bash
# Option A: via git
pkg install -y git
git clone https://github.com/your-username/melt
cd melt

# Option B: via USB/ADB (push the melt folder to ~/storage/downloads/ first)
cp -r ~/storage/downloads/melt ~/
cd melt
```

### 7. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 8. Run it

```bash
python main.py
```

Or set up the `melt` command:

```bash
mkdir -p $PREFIX/bin
cat > $PREFIX/bin/melt << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$(readlink -f "$0")")/.."
python main.py "$@"
EOF
chmod +x $PREFIX/bin/melt
```
Then just type: `melt`

### Using the setup script

If you already copied the project, you can also run the automated script:

```bash
chmod +x BUILD_TERMUX.sh
./BUILD_TERMUX.sh
```

This runs steps 3-5 and 7-8 automatically.

### Notes

- **Storage:** Downloads save to the `melt/downloads/` folder inside Termux. To access them from your phone's file manager, symlink:
  ```bash
  ln -s ~/melt/downloads ~/storage/downloads/melt-downloads
  ```
- **Sound notifications:** Requires Termux:API (step 5). The app uses `termux-notification --sound` for sound events.
- **Node.js:** Optional but speeds up yt-dlp ~2x. Without it, Python-based extraction is used (slower).

---

## Node.js (Optional)

For best yt-dlp performance:
- **Windows:** `scoop install nodejs`
- **macOS:** `brew install node`
- **Linux:** `sudo apt install nodejs`
- **Termux:** `pkg install nodejs`

If Node.js is not installed, yt-dlp falls back to Python-based extraction (slower but works).

---

## Verify

```bash
python main.py --help
python main.py --version
# or for built binaries:
bin\windows\melt.exe --help
bin\windows\melt.exe --version
bin/linux/melt --help
bin/linux/melt --version
```
