# MelT — Modern YouTube Downloader CLI

Download video, audio, and subtitles from YouTube with a modern CLI. Supports playlists, parallel downloads, thumbnail/subtitle embedding, SponsorBlock, and more.

## Quick Start

**Download from Releases (recommended):**
```
https://github.com/Agaroth0x1e/melt/releases
```
- `melt.exe` — Windows (standalone, ffmpeg bundled)
- `melt` — Linux (standalone, ffmpeg bundled)

**Install via pip:**
```
pip install https://github.com/Agaroth0x1e/melt/releases/download/v1.0.1/melt-1.0.1-py3-none-any.whl
```

**From source:**
```
pip install -r requirements.txt
python main.py
```

**Termux (Android):**
See [BUILD.md#termux-android](BUILD.md#termux-android) for full setup guide.

Pre-built binaries bundle ffmpeg. Source mode requires ffmpeg in PATH (`scoop install ffmpeg` / `brew install ffmpeg` / `sudo apt install ffmpeg`).

## Inline Help

Type `help` at the URL prompt for detailed guidance on usage, shortcuts, and session-persistent options.

## Session-Persistent Options

After your first download, MelT remembers your settings (format, destination, numbering, duplicate action, dry run) and asks if you want to reuse them for the next batch:

```
Previous session settings:
  Format:        Audio
  Destination:   downloads\audio
  Numbering:     No
  On Duplicate:  skip
  Dry Run:       No
Reuse these settings? (Y=yes / n=no / s=show again / q=quit) (default: yes):
```

- **Enter/Y** — reuse the same settings
- **n** — choose new settings
- **s** — show the summary again
- **q** — quit

Settings reset to defaults when you close and reopen MelT. Playlist ranges are always prompted fresh (each playlist is different).

## Features

- Single video & playlist downloads
- Multi-URL support (paste space-separated URLs)
- Batch file loading (`@file.txt`)
- Video (mp4) or Audio (m4a) with thumbnail embedding
- Subtitle download with roll-up caption cleaning
- Subtitle embedding into video/audio
- Parallel downloads (configurable threads)
- SponsorBlock integration (auto-skip sponsored segments)
- Dry-run mode to preview before downloading
- Download queue persistence (resume crashes with `--resume`)
- Rate limiting, cookies file support, archive dedup
- Session-persistent options (reuse settings between batches)
- Standalone .exe with bundled ffmpeg

## Usage

```bash
python main.py                    # Interactive mode
python main.py --resume           # Resume interrupted queue
python main.py --help             # Show help
python main.py --version          # Show version
```

### Session Behavior

- Settings are remembered within a session (app open → app close).
- Close and reopen MelT to reset to config defaults.
- Playlist ranges are always prompted per playlist — never reused.

### Multi-URL

```
Enter YouTube URL: https://youtu.be/A https://youtube.com/playlist?list=XYZ
```

### Batch file

```
Enter YouTube URL: @videos.txt
```

File format (one URL per line, `#` for comments):
```
https://youtu.be/A
https://youtube.com/playlist?list=XYZ
# This line is ignored
```

## Configuration

Edit `config/config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `max_threads` | `3` | Parallel downloads |
| `default_format` | `"video"` | `"video"` or `"audio"` |
| `clear_temp` | `true` | Delete temp files after download |
| `numbering` | `false` | Prepend index to filenames |
| `duplicate_action` | `"skip"` | `"skip"`, `"overwrite"`, or `"keep"` |
| `sponsorblock` | `true` | Skip sponsored segments |
| `dry_run` | `false` | Preview without downloading |
| `exit_on_complete` | `false` | Exit after download (false = loop back) |
| `default_reuse` | `true` | Default to reuse previous settings (false = always prompt fresh) |
| `reverse_playlist` | `false` | Process newest-first |
| `rate_limit` | `""` | e.g. `"5M"`, empty = unlimited |
| `cookies_file` | `""` | Path to cookies.txt |
| `playlist_folder_template` | `"%(playlist_title)s"` | Subfolder naming for playlists |
| `timeout_seconds` | `5` | Seconds before auto-confirm prompts (`-1` = no timeout) |
| `video.preferred_format` | `"mp4"` | `"mp4"`, `"mkv"`, or `"webm"` |
| `video.quality_priority` | `["480","360","720"]` | Preferred resolutions |
| `video.preferred_codec` | `"h264"` | `"h264"`, `"h265"`, or `"vp9"` |
| `audio.preferred_format` | `"m4a"` | `"m4a"`, `"mp3"`, or `"opus"` |
| `audio.quality_priority` | `["128","192","264"]` | Preferred bitrates |
| `audio.default_quality` | `128` | Fallback bitrate |
| `subtitle.prefer_human` | `true` | Prefer human subs over auto |
| `subtitle.language` | `"en"` | Language code |
| `subtitle.preferred_format` | `"srt"` | `"srt"`, `"vtt"`, or `"ass"` |

## Build from Source

See [BUILD.md](BUILD.md) for platform-specific build instructions.

## Requirements

- Python 3.8+
- ffmpeg (bundled in .exe, system install for source)
- Node.js (optional, 2x yt-dlp speed)
