# MelT Project Context

## Identity
- Project: **MelT** — Python CLI tool for downloading YouTube video/audio/subtitles
- PyPI: `meltdl` v1.1.0 (note: `melt` and `melty` were taken)
- GitHub: `Agaroth0x1e/melt` (note: repo name is `melt`, NOT `YT-DL`)
- License: MIT
- Local path: `C:\Users\USER\Documents\Projects\MelT`
- Entry point: `main.py` (VERSION = '1.1.0')
- Orchestrator: `mother_script.py`

## What Is Here
All source files are directly in the project root:
- `main.py` — entry point, CLI flags, `find_ffmpeg()`, `check_nodejs()`
- `mother_script.py` — orchestration, main menu loop, search, analytics, dashboard, schedule, rules, watch, sync
- `components/` — `downloader.py`, `subcleaner.py`, `remuxer.py`
- `utils/` — `config.py`, `logger.py`, `archive.py`, `failed.py`, `skipped.py`, `cli.py`, `notification.py`, `stats.py`, `scheduler.py`, `watcher.py`, `sync.py`, `rules.py`, `tui.py`
- `sounds/` — 6 pre-made WAV files
- `tests/` — 31 pytest tests
- `config/` — auto-created on first run (gitignored): `config.json`, `schedule.json`, `rules.json`, `profiles/`, `sync/`
- `logs/`, `downloads/`, `temp/`, `watch/` — auto-created runtime dirs (gitignored)
- `pyproject.toml` — package config
- `.gitignore` — covers all runtime dirs + Python/OS/IDE artifacts
- `AGENTS.md` — this file

## Build & Deploy
- **Build .exe:** `pyinstaller --onefile --windowed --name melt --add-data "sounds;sounds" --add-data "ffmpeg.exe;." main.py`
- **Build Linux/macOS:** done via GitHub Actions workflow `.github/workflows/build.yml`
- **Release:** binaries uploaded to GitHub Releases page (not in git)
- **PyPI publish:** `flit build` + `flit publish` or `python -m build && twine upload dist/*`

## Architecture

### Entry Flow
1. `main.py` parses args: `--help`/`-h`, `--version`, `--resume`, `--profile <name>`
2. Calls `MotherScript(config).run()` which shows the interactive main menu
3. Menu options: 1=Download, 2=Search, 3=Analytics, 4=Dashboard, 5=Schedule, 6=Rules, 7=Watch, 8=Sync, 9=Help, 0=Exit
4. Menu table shown only on first iteration; subsequent loops show just `Choose an option:`

### Download Flow (`_run_download_flow`)
1. Prompt: `Enter YouTube URL or URLs:` (space-separated or `@file.txt` for batch)
2. Each URL inspected via yt-dlp flat extraction (`extract_flat.inspect` from config)
3. For playlists: show video count + prompt for range (always prompted fresh per playlist)
4. After ALL URLs analyzed: show summary with counts, then `Press Enter to start or [m] to modify options`
5. Modify sub-menu: Format, Quality, Destination, Codec, Language, Subtitle, Dry Run, Numbering, SponsorBlock, Preview, Merge, Chapters, Reuse, Timeout, Rate Limit, Duplicate Action
6. Dry Run: logs what would download without actually downloading
7. Downloads run in parallel (threaded via `concurrent.futures`)
8. After complete: summary panel, sounds play, then either exit or continue prompt
9. Continue prompt offers `Y/n/m/s/q` — accepts "menu" via prefix match ("men" works)
10. Settings persist for session via `_prev_settings`; next URL entry shows reuse prompt

### Search Flow (`_run_search`)
- Uses `ytsearchN:query` (default N=30 from config `search.default_results`)
- Rich table: #, Type [V]/[P], Title, Channel, Date (relative), Duration, Views
- Type `more` to fetch next 30
- Filtered/sorted via `search` config: `filter_type` (all/video/playlist), `default_sort` (relevance/views/date/duration)
- Uses `upload_date` (YYYYMMDD) parsed by `_rel_date()` which handles int and str
- `extract_flat.search` config key controls whether flat extraction is used (default: false)

### Config (`utils/config.py`)
- File: `config/config.json` (auto-created with defaults on first run)
- Key settings:
  - `clear_temp` (bool), `exit_on_complete` (bool, false=loop back to URL), `rate_limit` (str or false)
  - `cookies_file` (str or false), `sponsorblock` (bool), `reverse_playlist` (bool)
  - `playlist_folder_template` (str), `prefer_human` (bool)
  - Quality priorities: `quality_video`, `quality_audio` (arrays), `preferred_codec` (av1/vp9/h264/h265/any)
  - `language` (str, default 'en'), `numbering` (bool), `duplicate_action` (skip/overwrite/keep)
  - `timeout_seconds` (int, -1 = no timeout), `enable_sounds` (bool)
  - `default_reuse` (bool), `format_preview` (bool)
  - `merge_mode` (bool), `watch_folder` (object with `enabled`, `interval`, `default_format`, `default_dest`)
  - `chapter_splitter` (object with `enabled`), `search` (object with `default_results`, `filter_type`, `default_sort`)
  - `extract_flat` (object with `inspect` [default true], `search` [default false])
  - `sounds` (object with 6 override paths)
- `dry_run` is NOT in config — it's a runtime toggle via modify menu (press `m` at start prompt)
- Config validation runs at startup

### yt-dlp Integration
- Wrapper in `components/downloader.py`
- Format priority strings based on preferred codec
- Subtitle download + SponsorBlock + rate limiting + cookies
- `ffmpeg_location` set via `_ffmpeg_location_opts()` based on `find_ffmpeg()` result
- `is_playlist` / `inspect_url` use `extract_flat: self._flat` from config

### Post-Download
- **SubCleaner** (`components/subcleaner.py`): removes roll-up captions
- **Remuxer** (`components/remuxer.py`): ffmpeg conversion, subtitle embedding (video path), chapter split
- **Audio subtitles:** embedded as `mov_text` track + `©lyr` MP4 metadata via `mutagen`
- **Audio path does NOT download subtitles** anymore (video path only)
- **Chapters:** `split_by_chapters` + `get_chapters` via ffprobe; keeps original; non-fatal
- **Merge mode:** downloads video-only + audio-only separately then merges
- **Duplicate check:** format-aware file-exists check; `archive.txt` is write-only history log
- **Per-entry `job_dir` cleaned up immediately after each entry finishes**

### Error Handling
- **Invalid URLs:** simple `WARN Invalid URL: <url>` and re-prompt — no verbose trace or 0-item summary
- **Subtitle failure:** non-fatal, counted separately in completion panel
- **Cookies:** only via config file path — no terminal prompt
- **Subtitle fallback:** prefer human subs, fall back to auto when unavailable

### Special Features
- **Scheduled Downloads** (`utils/scheduler.py`): `melt schedule add/list/remove/daemon`; jobs in `config/schedule.json`
- **Auto-Rules** (`utils/rules.py`): `melt rule add --channel/keyword/url --fmt/dest`; matches title/uploader/url regex
- **Watch Folder** (`utils/watcher.py`): `melt watch`; monitors folder for URL files; aborts via `T`/`Ctrl+T` keypress polling (not Ctrl+C); `[Watch]` prefix in output
- **Analytics** (`utils/stats.py`): `melt analytics`; overview, format breakdown, month bar chart, last 10
- **TUI Dashboard** (`utils/tui.py`): `melt dashboard`; full-screen Rich Live; uses `msvcrt.kbhit()` on Windows, `select.select()` on Unix; catches all exceptions inside Live context to restore terminal
- **Cloud Sync** (`utils/sync.py`): `melt sync init/push/pull/status`; dedicated git repo at `config/sync/.git`
- **Style Profiles:** `melt profile save/list/delete/show`; `--profile <name>`; saved as `config/profiles/<name>.json`
- **Collaborative Queue:** `melt export <file>` / `melt import <file>`; `.meltqueue` JSON format: `{"version":1,"urls":[...],"fmt":"...","dest":"..."}`
- **Format Preview:** `format_preview: true` in config; fetches formats via full extract right before download; user picks ID or Enter for auto
- **Sound notifications:** 6 WAV sounds; each overrideable via `sounds` config section; finds ffplay/ffmpeg from bundled or system PATH
- **Playlist Diff:** snapshot-based at `logs/playlist_snapshots/<id>.json`; shows `+N new / -M removed`
- **Default destination:** auto-splits into `downloads/videos/` or `downloads/audio/` (only when dest matches config's `downloads_dir` and format != 'both')
- **Timeout:** auto-starts only when no key is pressed; Windows uses `msvcrt.kbhit()`, Unix/Mac uses `select.select()`; `-1` = no timeout
- **Logging:** all user actions logged to `logs/log.txt` (menu choices, search queries, URL entries, option modifications, sub-menu actions, download results, exits)
- **Banner:** minimalist — just `MelT` + `v1.1.0` in a small bordered box
- **Resume:** `--resume` flag loads `_resume_queue.json` from config working dir

### Bundling
- `_is_bundled()` checks `getattr(sys, 'frozen', False)` (PyInstaller)
- `_bundle_dir()` returns `sys._MEIPASS` when frozen, else script dir
- `_exe_dir()` returns `os.path.dirname(sys.executable)` when frozen, else script dir
- `find_ffmpeg()`: when bundled, checks `_bundle_dir()/ffmpeg.exe` → `_exe_dir()/ffmpeg.exe` → system PATH
- `os.environ['FFMPEG_PATH']` only set in standalone builds

### v1.1.0 — Shipped ✅
- Feature-complete per original plan
- Published to PyPI: `meltdl` v1.1.0
- GitHub release with 3 platform binaries: `melt.exe` (Win), `melt-linux` (Linux), `melt-macos` (macOS CLI binary, no `.dmg`)
- macOS CLI tool ships as a plain binary (no extension) — standard for CLI tools on macOS; `.dmg` is for GUI `.app` bundles

### Build Workflow
- `.github/workflows/build.yml` triggers on `workflow_dispatch` (with `tag` input) or `release: [published]`
- Builds Windows (`melt.exe`), Linux (`melt-linux`), macOS (`melt-macos`) binaries with bundled ffmpeg + sounds
- Linux installs ffmpeg via apt (johnvansickle.com is dead)
- macOS downloads ffmpeg from evermeet.cx
- Windows downloads ffmpeg from gyan.dev
- Uses `gh release upload ${{ env.TAG }}` — distinct names per platform to avoid collisions
- `GITHUB_TOKEN` with `contents: write` permission handles auth

## Key Decisions (Historical)
- Interactive main menu replaces direct URL prompt entry
- Watch folder uses keypress polling (T/Ctrl+T) not Ctrl+C
- Dashboard uses `msvcrt.kbhit()` on Windows (`select.select()` only works with sockets)
- Search date uses `upload_date` not `timestamp` (absent with flat extraction)
- `extract_flat` split into two config keys: `inspect` and `search`
- Invalid URLs get simple warning + re-prompt
- Project root contains only source code; all runtime dirs auto-generated and gitignored
- `dry_run` removed from config — runtime toggle via modify menu
- Audio uses m4a with `mov_text` subtitle embedding + `©lyr` metadata via `mutagen`
- macOS CLI binary has no extension (`.dmg` is for GUI apps only)
- Linux binary named `melt-linux`, macOS named `melt-macos`, Windows `melt.exe` — distinct names prevent release asset collisions
