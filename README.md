# MelT — YouTube Downloader CLI

Download video, audio, and subtitles from YouTube with parallel processing, subtitle cleaning, SponsorBlock, chapter splitting, scheduled downloads, and more. Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) with a polished [Rich](https://github.com/Textualize/rich) interface.

```
pip install meltdl
python -c "import melt"  # or just: melt
```

**Source mode** requires ffmpeg in PATH (`scoop install ffmpeg` / `brew install ffmpeg` / `sudo apt install ffmpeg`).

---

## Quick Start

```bash
python main.py                        # Interactive mode
python main.py --help                 # Full help reference
python main.py --version              # Show version
python main.py --resume               # Resume interrupted queue
python main.py --profile <name>       # Load a saved profile
```

### Batch commands

| Command | Description |
|---------|-------------|
| `melt search <query>` | Search YouTube and download |
| `melt analytics` | Show download statistics |
| `melt schedule <add/list/remove/daemon>` | Scheduled downloads |
| `melt rule <add/list/remove>` | Auto-rules by channel/keyword/URL |
| `melt watch` | Watch folder for URL files |
| `melt profile <save/list/delete/show>` | Config profiles |
| `melt export/import <file>` | Collaborative queues |
| `melt sync <init/push/pull/status>` | Cloud sync config via git |

---

## Interactive Workflow

### Entering URLs

```
Enter YouTube URL or URLs: https://youtu.be/abc123 https://youtube.com/playlist?list=XYZ
```

- **Multi-URL** — space-separated
- **Batch files** — `@file.txt` (one per line, `#` comments)
- **Type `help`** for inline reference

### Format selection

| Choice | What happens |
|--------|-------------|
| `1` (Video) | Best video+audio + subtitles + thumbnail → `downloads/videos/` |
| `2` (Audio) | Best audio + lyrics metadata → `downloads/audio/` |
| `3` (Both) | Video AND audio downloaded simultaneously |

```
Download format (1: video, 2: audio, 3: both) (default: video): 3
```

### Session persistence

After the first download, MelT remembers your settings so you don't re-enter them:

```
Reuse these settings? (Y=yes / n=no / m=modify / s=show / q=quit):
```

- `Y` / Enter — reuse
- `n` — enter fresh options
- `m` — modify specific options
- `q` — quit

### Modify menu

Press `m` at the start prompt to change any option before downloading:

```
Select option to modify:
  [1] Items
  [2] Format              (video / audio / both)
  [3] Destination
  [4] Numbering           (toggle on/off)
  [5] On Duplicate        (skip / overwrite / keep)
  [6] Archive Action      (skip / ask / redownload)
  [7] Dry Run             (toggle on/off)
  [8] Start download
```

### Dry Run

Toggle on via the **modify menu** (`m` then select `Dry Run`). Previews what would download without actually downloading — shows files, sizes, and destinations.

### Format Preview

When enabled in config, shows all available formats before download:

```
Available formats for "Video Title":
┌─────┬──────┬───────┬────────┬────────┬──────────┐
│ ID  │ Ext  │ Type  │ Quality│ Codec  │ Size     │
├─────┼──────┼───────┼────────┼────────┼──────────┤
│ 137 │ mp4  │ video │ 1080p  │ avc1   │ 450.2 MB │
│ 136 │ mp4  │ video │ 720p   │ avc1   │ 180.5 MB │
│ 140 │ m4a  │ audio │ 128k   │ mp4a   │ 5.2 MB   │
└─────┴──────┴───────┴────────┴────────┴──────────┘
Enter format ID to use (or press Enter for auto):
```

Set `"format_preview": true` in `config/config.json`. Zero cost when disabled.

---

## Features

### Parallel Downloads

Configure `max_threads` in config. Multiple downloads run simultaneously.

### Duplicate Handling (`duplicate_action`)

| Setting | Behavior |
|---------|----------|
| `skip` | Skip if file exists at destination, log to `logs/skipped.txt` |
| `overwrite` | Overwrite existing file |
| `keep` | Append counter (`file_1.mp4`, `file_2.mp4`) |

### Archive Handling (`archive_action`)

Check is per-item, after duplicate check. Only applies when file is **missing** from disk but its ID is in `archive.txt` (e.g. user deleted the file but archive still has the record).

| Setting | Behavior |
|---------|----------|
| `skip` | Auto-skip after `archive_timeout` seconds (default 10). Press `r` to redownload |
| `ask` | Always prompt — no timeout, waits for Yes/No |
| `redownload` | Ignore archive, always download |

### Subtitle Cleaning

Auto-removes roll-up captions (cumulative on-screen text) from downloaded subtitles. Non-fatal on failure.

### SponsorBlock

Skip sponsored segments, intros, and outros automatically. Toggle via `"sponsorblock": true` in config.

### Merge Mode

When yt-dlp's internal merge fails, set `"merge_mode": true`. MelT downloads video + audio streams separately and merges with its own ffmpeg call.

### Chapter Splitter

Auto-split videos by chapter:

```json
"chapter_splitter": {
    "enabled": true,
    "output_template": "%(title)s - %(chapter)s.%(ext)s"
}
```

Creates: `Video Title - Introduction.mp4`, `Video Title - Main Content.mp4`, etc. Original file kept. Non-fatal on failure.

### Playlists

Auto-detects playlists and prompts for a range:

```
Fetching playlist: "My Playlist"...
Playlist range for "My Playlist" (e.g. 1-5, 1,3,5 or 'all') (default: all): 1-5
```

**Playlist Diff** — First download saves a snapshot. Next time, shows what changed:

```
Playlist changes: My Playlist
  + 3 new
    New Video Title 1
    New Video Title 2
  - 1 removed
    Removed Video Title
```

Settings: `"reverse_playlist": true` (newest first), `"playlist_folder_template": "%(playlist_title)s"`.

### Sound Notifications

6 built-in WAV sounds. Each overrideable in config:

```json
"sounds": {
    "batch_start": "C:/sounds/my-start.wav",
    "completion": ""
}
```

Empty string = bundled default. Disable all sounds with `"enable_sounds": false`.

### YouTube Search

Search and download directly from the CLI:

```
Choose an option: 2
Search YouTube: lofi hip hop beats

Search results: lofi hip hop beats
┌──────┬──────────────────────────────────┬──────────────────┬──────────┬──────────┬──────────┐
│ #    │ Type │ Title                      │ Channel          │ Date     │ Duration │ Views    │
├──────┼──────────────────────────────────┼──────────────────┼──────────┼──────────┼──────────┤
│ 1    │ [V]  │ lofi hip hop radio         │ Lofi Girl        │ 2w ago   │ 0:00     │ 50,000   │
│ 2    │ [V]  │ chill beats to relax       │ Chillhop         │ 5d ago   │ 3:45     │ 1,200    │
│ 3    │ [P]  │ Lo-Fi Beats Compilation    │ Chill Beats      │ 1mo ago  │ 1:30:00  │ 8,900    │
└──────┴──────────────────────────────────┴──────────────────┴──────────┴──────────┴──────────┘

Enter numbers to download (e.g. 1,3,5-8), 'all' for all, 'more' for next 30, or Enter to cancel:
```

Filter by type (`video` / `playlist` / `all`) and sort by (`relevance` / `views` / `date` / `duration`) in `search` config section. Type `more` to fetch the next 30 results.

---

## Config Profiles

Save named config presets and switch between them:

```bash
melt profile save gaming      # Save current config as 'gaming'
melt profile list             # List saved profiles
melt profile show gaming      # View a profile
melt profile delete gaming    # Delete a profile
melt --profile gaming         # Start with 'gaming' profile
```

Profiles stored at `config/profiles/<name>.json`.

---

## Auto-Rules

Define rules that auto-match and override format/destination:

```bash
melt rule add --keyword "tutorial" --fmt audio --dest podcasts
melt rule add --channel "MyChannel" --fmt video --dest "my-channel-downloads"
melt rule add --url "live" --fmt both
melt rule list
melt rule remove <id>
```

Rules match against title, channel/uploader, or URL pattern (regex). Stored in `config/rules.json`.

---

## Scheduled Downloads

Schedule recurring downloads with the built-in daemon:

```bash
melt schedule add https://youtube.com/playlist?list=XYZ --interval 24
melt schedule list
melt schedule remove <id>
melt schedule daemon
```

- `--interval N` — run every N hours
- `--fmt FMT` — format override
- `--dest PATH` — destination override
- Single-run jobs (interval 0) auto-disable after execution

Daemon checks every 60 seconds. Jobs stored in `config/schedule.json`.

---

## Watch Folder

Drop URL files into a folder and MelT auto-downloads them:

```bash
melt watch
```

Config:

```json
"watch_folder": {
    "enabled": false,
    "path": "watch",
    "interval_seconds": 60,
    "auto_delete": true,
    "default_format": "video",
    "default_dest": "downloads"
}
```

- **Stop:** press `T` or `Ctrl+T`
- Any `.txt` file with URLs is auto-processed
- Trigger file deleted after processing (configurable)

---

## Download Analytics

```
Choose an option: 3

MelT Analytics
──────────────

┌──────────────────────────────────────┐
│ Overview                             │
├──────────────────────────────────────┤
│ Total downloads    42                │
│ Total size         2.3 GB            │
│ Average size       57.4 MB           │
│ Last download      2026-06-04 14:30  │
│ First download     2026-05-01 09:15  │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ By Month                             │
├────────┬───────────┬─────────────────┤
│ Month  │ Downloads │                  │
│ 2026-05│ 25        │ ████████████████ │
│ 2026-06│ 17        │ ███████████      │
└────────┴───────────┴─────────────────┘
```

Data tracked automatically at `logs/stats.json`.

---

## Collaborative Queue

Share download queues as `.meltqueue` JSON files:

```bash
melt export playlist.melt     # Export URLs + format + dest
melt import playlist.melt     # Import and start download
```

---

## Cloud Sync

Sync config, rules, schedules, profiles, and stats across machines via git:

```bash
melt sync init https://github.com/user/repo.git
melt sync push "updated rules"
melt sync pull
melt sync status
```

Uses a dedicated git repo at `config/sync/.git`. Requires `git` in PATH.

---

## Configuration Reference

Full reference for `config/config.json`:

### General

> **Dry Run** is a runtime toggle via the modify menu (`m` at start prompt) — not a config key.

| Key | Default | Description |
|-----|---------|-------------|
| `max_threads` | `3` | Parallel download threads |
| `default_format` | `"video"` | `"video"`, `"audio"`, `"both"` |
| `clear_temp` | `true` | `true` / `false` |
| `numbering` | `false` | `true` / `false` |
| `duplicate_action` | `"skip"` | `"skip"` / `"overwrite"` / `"keep"` |
| `archive_action` | `"skip"` | `"skip"` (auto-skip after timeout) / `"ask"` (always prompt) / `"redownload"` (ignore archive) |
| `archive_timeout` | `10` | Seconds before auto-skip archived videos (positive integer) |
| `sponsorblock` | `true` | `true` / `false` |
| `exit_on_complete` | `false` | `true` / `false` |
| `default_reuse` | `true` | `true` / `false` |
| `reverse_playlist` | `false` | `true` / `false` |
| `format_preview` | `false` | `true` / `false` |
| `merge_mode` | `false` | `true` / `false` |
| `rate_limit` | `""` | e.g. `"5M"`, empty = unlimited |
| `cookies_file` | `""` | Path to cookies.txt |
| `cookies_from_browser` | `""` | Browser name: `"chrome"`, `"firefox"`, `"edge"`, etc. |
| `proxy` | `""` | `"http://host:port"`, `"socks5://host:port"`, or `"auto"` (scans system + local ports) |
| `timeout_seconds` | `5` | Auto-confirm timeout (`-1` = no timeout, positive int = seconds) |
| `enable_sounds` | `true` | `true` / `false` |
| `extract_flat.inspect` | `true` | `true` / `false` |
| `extract_flat.search` | `false` | `true` / `false` |

### WARP Tunnel

| Key | Default | Description |
|-----|---------|-------------|
| `warp` | `false` | `true` / `false` — Enable built-in WARP tunnel via wireproxy (SOCKS5 :1080) |
| `warp_location` | `""` | Request egress IP region: `"us"`, `"jp"`, `"gb"`, `"fr"`, `"de"`, `"sg"`, `"au"`, `"br"`, or `""` (auto). Re-registers until a matching egress is assigned |

### Video

| Key | Default | Available values |
|-----|---------|-----------------|
| `preferred_format` | `"mp4"` | `"mp4"`, `"mkv"`, `"webm"` |
| `quality_priority` | `["480","360","720"]` | Any resolution numbers, ordered by preference |
| `preferred_codec` | `"h264"` | `"h264"`, `"h265"`, `"vp9"`, `"av1"`, `"any"` |

### Audio

| Key | Default | Available values |
|-----|---------|-----------------|
| `preferred_format` | `"m4a"` | `"m4a"`, `"mp3"`, `"opus"` |
| `quality_priority` | `["128","192","264"]` | Any bitrate numbers, ordered by preference |
| `default_quality` | `128` | Fallback bitrate (integer) |

### Subtitle

| Key | Default | Available values |
|-----|---------|-----------------|
| `prefer_human` | `true` | `true` / `false` |
| `language` | `"en"` | Single code or comma-separated: `"en,ja,es"`. Available codes: `ar`, `da`, `de`, `el`, `en`, `es`, `fi`, `fr`, `he`, `hi`, `hu`, `id`, `it`, `ja`, `ko`, `nl`, `no`, `pl`, `pt`, `ro`, `ru`, `sv`, `th`, `tr`, `uk`, `vi`, `zh-Hans`, `zh-Hant` |
| `preferred_format` | `"srt"` | `"srt"`, `"vtt"`, `"ass"` |
| `transliterate` | `""` | `""` (keep original) / `"romaji"` (convert non-Latin scripts to romanized form) |

### Watch Folder

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Enable watch folder |
| `path` | `"watch"` | Folder to monitor |
| `interval_seconds` | `60` | Scan interval |
| `auto_delete` | `true` | Delete trigger files after processing |
| `default_format` | `"video"` | Format for watch downloads |
| `default_dest` | `"downloads"` | Destination for watch downloads |

### Chapter Splitter

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Auto-split videos by chapter |
| `output_template` | `"%(title)s - %(chapter)s.%(ext)s"` | Naming template |

### Search

| Key | Default | Available values |
|-----|---------|-----------------|
| `filter_type` | `"all"` | `"all"`, `"video"`, `"playlist"` |
| `default_sort` | `"relevance"` | `"relevance"`, `"views"`, `"date"`, `"duration"` |
| `default_results` | `30` | Number of search results per page |

### Sounds

| Key | Default | Description |
|-----|---------|-------------|
| (6 event keys) | `""` | WAV path or empty for bundled default |

---

## Requirements

- Python 3.8+
- ffmpeg (bundled in standalone builds, system install for source)
- Node.js (optional — enables 2x yt-dlp speed)
- git (optional — for cloud sync)

---

## License

MIT
