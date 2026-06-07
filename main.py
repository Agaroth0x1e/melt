#!/usr/bin/env python3
import os
import sys
import time
import json
import subprocess

VERSION = '1.3.0'

HELP_TEXT = f"""
MelT v{VERSION}

USAGE:
  python main.py                          Interactive mode (default)
  python main.py --help / -h              Show this help message
  python main.py --version                Show version
  python main.py --resume                 Resume interrupted download queue
  python main.py --profile <name>         Load a saved config profile

  [BATCH COMMANDS]
  python main.py profile <action> [name]  Manage config profiles
  python main.py rule <action> [args]     Manage auto-rules
  python main.py schedule <action> [args] Manage scheduled downloads
  python main.py search <query>           Search YouTube and download
  python main.py watch                    Watch folder for URL files
  python main.py dashboard / tui          Open TUI dashboard
  python main.py analytics / stats        Show download statistics
  python main.py sync <action> [args]     Cloud sync via git
  python main.py export <file>            Export URLs as .meltqueue
  python main.py import <file>            Import URLs from .meltqueue

DESCRIPTION:
  MelT is a modern YouTube downloader CLI built on yt-dlp and Rich.
  It wraps yt-dlp with parallel processing, subtitle cleaning,
  thumbnail embedding, SponsorBlock, playlists, dry-run mode,
  queue persistence, sound notifications, format preview,
  style profiles, auto-rules, scheduled downloads, watch folders,
  collaborative queues, and a TUI dashboard.

FEATURES:

  [1] Core Download
  - Single video, playlists, multi-URL (space-separated), batch files (@file.txt)
  - Format: Video (1), Audio (2), or Both (3 — downloads video+audio in parallel)
  - Auto-sorted into downloads/videos/ and downloads/audio/
  - Parallel downloads via thread pool (configurable max_threads)
  - Thumbnail embedding for both video and audio
  - Subtitle download with roll-up caption cleaning and SRT conversion
  - SponsorBlock integration (auto-marks sponsored segments)
  - Rate limiting and cookies file support
  - Duplicate detection: skip / overwrite / keep (auto-counter)
  - Dry-run mode: preview without downloading

  [2] Playlist & Diff
  - Auto-detects playlists, asks for range (e.g. 1-5, 3,7-10, all)
  - Playlist snapshot system — first time you download a playlist,
    MelT saves its video list. Next time, it shows what's new (+N)
    and what's removed (-M). Updated after every fetch.
  - Optional reverse_playlist, playlist_folder_template

  [3] Format Preview
  - Set format_preview: true in config to see a Rich table of
    available formats before each download. Pick a format ID to
    override auto-selection, or press Enter to let yt-dlp decide.

  [4] Merge Mode
  - Set merge_mode: true to download video and audio streams
    separately and merge them with MelT's own ffmpeg call.
    Useful when yt-dlp's internal merge fails.

  [5] Chapter Splitter
  - Set chapter_splitter.enabled: true to auto-split downloaded
    videos into per-chapter files (named Title - Chapter Name.mp4).
    Original file is kept. Non-fatal on failure.

  [6] Session Persistence
  - After first batch, MelT remembers your settings and offers
    to reuse: Y=yes, n=no, m=modify, s=show, q=quit
  - Queue persistence: interrupted downloads resume with --resume

  [7] Sound Notifications
  - 6 configurable sounds (batch_start, analyze_complete,
    download_error, aborting, fatal_error, completion)
  - Each overridable via config sounds section (WAV files)
  - Uses ffplay or ffmpeg for playback

  [8] Style Profiles
  - python main.py profile save <name>   Save current config as preset
  - python main.py profile list          List saved profiles
  - python main.py profile show <name>   View a profile
  - python main.py profile delete <name> Delete a profile
  - python main.py --profile <name>      Start with a profile loaded

  [9] Auto-Rules
  - python main.py rule add --keyword "tutorial" --fmt audio --dest music
    Matches downloads by keyword in title, channel name, or URL pattern,
    and auto-applies format and/or destination.
  - python main.py rule add --channel "ChannelName" --fmt video
  - python main.py rule add --url "pattern" --fmt both
  - python main.py rule list     View all rules
  - python main.py rule remove <id>  Remove a rule

  [10] Scheduled Downloads
  - python main.py schedule add URL --interval 24
    Downloads the URL every 24 hours.
  - python main.py schedule add URL --at 08:00 --fmt audio
    Downloads daily at 8 AM.
  - python main.py schedule list    View all scheduled jobs
  - python main.py schedule remove <id>   Remove a job
  - python main.py schedule daemon   Run scheduler loop (checks every 60s)
    Single-run jobs auto-disable after first execution.

  [11] Watch Folder
  - python main.py watch
    Monitors a folder (config: watch_folder.path, default "watch/")
    for URL files. Any file containing URLs is read and auto-downloaded.
    Trigger files are deleted after processing. Checks every N seconds
    (config: watch_folder.interval_seconds).

  [12] YouTube Search
  - python main.py search "query"
    Searches YouTube via yt-dlp, shows up to 30 results in a Rich table
    (title, channel, duration, views). Enter indices (1,3,5-8), "all",
    or Enter to cancel. Selected results go straight to download queue.

  [13] Download Analytics
  - python main.py analytics
    Shows total/downloads, total/average size, format breakdown,
    month-by-month bar chart, and last 10 downloads.
    Data is tracked from every successful download.

  [14] Cloud Sync
  - python main.py sync init <remote-url>
    Initializes a dedicated git repo at config/sync/ that tracks
    config, rules, schedule, profiles, stats, and playlist snapshots.
  - python main.py sync push [message]   Commit + push changes
  - python main.py sync pull             Pull latest changes
  - python main.py sync status           Show git status + recent commits

  [15] TUI Dashboard
  - python main.py dashboard
    Full-screen Rich TUI with live stats panel, recent downloads table,
    and keyboard controls (q=quit, r=refresh, d=open downloads folder).

  [16] Collaborative Queue
  - python main.py export queue.melt
    Exports URLs + format + destination to a shareable .meltqueue file.
  - python main.py import queue.melt
    Imports URLs from a .meltqueue file and starts download.

INLINE HELP:
  Type "help" at the URL prompt for detailed interactive guidance.

SHORTCUTS:
  q / quit / exit    Exit at most prompts
  help               Show inline help (at URL prompt)
  m                  Modify options before starting
  Enter              Accept default / auto-confirm
  Ctrl+C             Abort current batch immediately

REQUIREMENTS:
  - ffmpeg (bundled in .exe, or system install via scoop/brew/apt/pkg)
  - Node.js (optional — enables 2x yt-dlp speed)
  - git (optional — required for cloud sync)

CONFIGURATION:
  All defaults in config/config.json:
    general.format, max_threads, timeout_seconds (-1 = no timeout),
    numbering, duplicate_action (skip/overwrite/keep),
    exit_on_complete, sponsorblock, reverse_playlist, enable_sounds,
    default_reuse, format_preview, merge_mode
    watch_folder (path, interval_seconds, auto_delete)
    chapter_splitter (enabled, output_template)
  Video/audio quality priorities, preferred_format, preferred_codec
  Subtitle language, prefer_human, preferred_format
  Sound profiles (override bundled WAVs)

EXAMPLES:
  python main.py                                  Start interactive session
  python main.py --resume                         Resume interrupted queue
  python main.py --profile gaming                 Start with 'gaming' profile

  python main.py profile save work                Save current config
  python main.py profile list                     List saved profiles

  python main.py search "lofi hip hop"            Search and download
  python main.py analytics                        View download stats
  python main.py dashboard                        Open TUI dashboard

  python main.py rule add --keyword tutorial --fmt audio --dest podcasts
  python main.py rule list

  python main.py schedule add URL --interval 24   Download every 24h
  python main.py schedule daemon                  Start scheduler
  python main.py watch                            Start folder watcher

  python main.py sync init https://github.com/user/repo.git
  python main.py sync push "updated rules"
  python main.py sync status

  python main.py export batch.melt                Export queue
  python main.py import batch.melt                Import queue
"""


def _is_bundled():
    return getattr(sys, 'frozen', False)


def _bundle_dir():
    if _is_bundled():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _exe_dir():
    if _is_bundled():
        return os.path.abspath(os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def find_ffmpeg():
    if _is_bundled():
        ffmpeg_name = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
        locations = [
            os.path.join(_bundle_dir(), ffmpeg_name),
            os.path.join(_exe_dir(), ffmpeg_name),
            'ffmpeg',
        ]
        for loc in locations:
            try:
                r = subprocess.run(
                    [loc, '-version'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                if r.returncode == 0:
                    return loc
            except FileNotFoundError:
                continue
        return None
    return 'ffmpeg'


def check_nodejs():
    try:
        r = subprocess.run(
            ['node', '--version'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return r.returncode == 0
    except FileNotFoundError:
        return False


def show_help():
    print(HELP_TEXT)
    sys.exit(0)


def main():
    if '-h' in sys.argv or '--help' in sys.argv:
        show_help()
    if '--version' in sys.argv:
        print(f"MelT v{VERSION}")
        sys.exit(0)

    resume = '--resume' in sys.argv

    profile_name = None
    for i, arg in enumerate(sys.argv):
        if arg == '--profile' and i + 1 < len(sys.argv):
            profile_name = sys.argv[i + 1]

    if len(sys.argv) >= 2 and sys.argv[1] == 'profile':
        cmd_args = sys.argv[2:]
        if not cmd_args or cmd_args[0] in ('help', '-h', '--help'):
            print("Usage: melt profile <save|list|delete|show> [name]")
            sys.exit(0)
        action = cmd_args[0]
        from utils.config import Config
        cfg = Config()
        profiles_dir = cfg.resolve_path(os.path.join(os.path.dirname(cfg.config_path), 'profiles'))
        os.makedirs(profiles_dir, exist_ok=True)
        if action == 'list':
            for f in sorted(os.listdir(profiles_dir)):
                if f.endswith('.json'):
                    name = f[:-5]
                    print(f"  {name}")
            sys.exit(0)
        if len(cmd_args) < 2:
            print(f"Usage: melt profile {action} <name>")
            sys.exit(1)
        name = cmd_args[1]
        path = os.path.join(profiles_dir, f"{name}.json")
        if action == 'save':
            import shutil
            shutil.copy2(cfg.config_path, path)
            print(f"Profile '{name}' saved")
            sys.exit(0)
        elif action == 'delete':
            if os.path.exists(path):
                os.remove(path)
                print(f"Profile '{name}' deleted")
            else:
                print(f"Profile '{name}' not found")
            sys.exit(0)
        elif action == 'show':
            if os.path.exists(path):
                with open(path) as f:
                    print(f.read())
            else:
                print(f"Profile '{name}' not found")
            sys.exit(0)
        else:
            print(f"Unknown action: {action}")
            sys.exit(1)

    if len(sys.argv) >= 2 and sys.argv[1] == 'rule':
        from utils.config import Config as RConfig
        from utils.logger import Logger as RLogger
        from utils.rules import RuleManager
        r_cfg = RConfig()
        r_log = RLogger(r_cfg.resolve_path(r_cfg['general']['log_file']))
        rm = RuleManager(r_cfg, r_log)
        cmd_args = sys.argv[2:]
        if not cmd_args or cmd_args[0] in ('help', '-h', '--help'):
            print("Usage: melt rule <add|list|remove> [args]")
            print("  add             Add a new rule")
            print("    --channel CH    Match channel/uploader name")
            print("    --keyword KW    Match keyword in title")
            print("    --url PAT       Match URL pattern (regex)")
            print("    --fmt FMT       Format to apply (video/audio/both)")
            print("    --dest PATH     Destination to apply")
            print("  list             List all rules")
            print("  remove <id>      Remove a rule")
            sys.exit(0)
        action = cmd_args[0]
        if action == 'list':
            rules = rm.list()
            if not rules:
                print("No rules defined")
            else:
                for r in rules:
                    m = r.get('match', {})
                    a = r.get('action', {})
                    desc = []
                    if m.get('channel'): desc.append(f"channel={m['channel']}")
                    if m.get('keyword'): desc.append(f"keyword={m['keyword']}")
                    if m.get('url_pattern'): desc.append(f"url={m['url_pattern']}")
                    a_desc = []
                    if a.get('fmt'): a_desc.append(f"fmt={a['fmt']}")
                    if a.get('dest'): a_desc.append(f"dest={a['dest']}")
                    print(f"  [{r['id']}] {', '.join(desc)} -> {', '.join(a_desc)}")
            sys.exit(0)
        if action == 'remove':
            if len(cmd_args) < 2:
                print("Usage: melt rule remove <id>")
                sys.exit(1)
            if rm.remove(cmd_args[1]):
                print(f"Rule {cmd_args[1]} removed")
            else:
                print(f"Rule {cmd_args[1]} not found")
            sys.exit(0)
        if action == 'add':
            match = {}
            action_data = {}
            i = 1
            while i < len(cmd_args):
                if cmd_args[i] == '--channel' and i + 1 < len(cmd_args):
                    match['channel'] = cmd_args[i + 1]; i += 2
                elif cmd_args[i] == '--keyword' and i + 1 < len(cmd_args):
                    match['keyword'] = cmd_args[i + 1]; i += 2
                elif cmd_args[i] == '--url' and i + 1 < len(cmd_args):
                    match['url_pattern'] = cmd_args[i + 1]; i += 2
                elif cmd_args[i] == '--fmt' and i + 1 < len(cmd_args):
                    action_data['fmt'] = cmd_args[i + 1]; i += 2
                elif cmd_args[i] == '--dest' and i + 1 < len(cmd_args):
                    action_data['dest'] = cmd_args[i + 1]; i += 2
                else: i += 1
            if not match:
                print("At least one match criteria required (--channel, --keyword, --url)")
                sys.exit(1)
            rid = rm.add(match, action_data)
            print(f"Rule {rid} added")
            sys.exit(0)
        print(f"Unknown rule action: {action}")
        sys.exit(1)

    if len(sys.argv) >= 2 and sys.argv[1] == 'sync':
        from utils.config import Config as SyncConfig
        from utils.logger import Logger as SyncLogger
        from utils.sync import SyncManager
        sync_cfg = SyncConfig()
        sync_log = SyncLogger(sync_cfg.resolve_path(sync_cfg['general']['log_file']))
        sm = SyncManager(sync_cfg, sync_log)
        cmd_args = sys.argv[2:]
        if not cmd_args or cmd_args[0] in ('help', '-h', '--help'):
            print("Usage: melt sync <init|push|pull|status> [args]")
            print("  init [remote-url]  Initialize sync repository")
            print("  push [message]     Commit and push changes")
            print("  pull               Pull latest changes")
            print("  status             Show sync status")
            sys.exit(0)
        action = cmd_args[0]
        if action == 'init':
            remote = cmd_args[1] if len(cmd_args) > 1 else ''
            print(sm.init(remote))
            sys.exit(0)
        elif action == 'push':
            msg = ' '.join(cmd_args[1:]) if len(cmd_args) > 1 else ''
            print(sm.push(msg))
            sys.exit(0)
        elif action == 'pull':
            print(sm.pull())
            sys.exit(0)
        elif action == 'status':
            print(sm.status())
            print()
            print(sm.remote_status())
            sys.exit(0)
        else:
            print(f"Unknown sync action: {action}")
            sys.exit(1)

    if len(sys.argv) >= 2 and sys.argv[1] in ('analytics', 'stats'):
        from utils.config import Config as AConfig
        a_cfg = AConfig()
        from utils.stats import show_analytics
        show_analytics(a_cfg.resolve_path(os.path.join('logs', 'stats.json')))
        sys.exit(0)

    if len(sys.argv) >= 2 and sys.argv[1] == 'search':
        query = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ''
        if not query:
            query = input("Search YouTube: ").strip()
        if not query:
            sys.exit(0)
        import yt_dlp

        def _is_pl(e):
            ie = e.get('ie_key', '')
            url = e.get('url', '')
            return ie == 'YoutubePlaylist' or 'playlist?list=' in url or '/playlist?' in url

        def _rel_date(ud):
            if not ud:
                return ''
            from datetime import datetime
            try:
                if isinstance(ud, (int, float)):
                    d = datetime.fromtimestamp(ud)
                else:
                    d = datetime.strptime(str(ud), '%Y%m%d')
                diff = datetime.now() - d
                days = diff.days
                if days < 1: return 'today'
                if days == 1: return 'yesterday'
                if days < 7: return f'{days}d ago'
                if days < 30: return f'{days // 7}w ago'
                if days < 365: return f'{days // 30}mo ago'
                return f'{days // 365}y ago'
            except Exception:
                return ''

        from utils.config import Config as SConfig
        s_cfg = SConfig()
        sc = s_cfg.get('search', {})
        filter_type = sc.get('filter_type', 'all')
        default_sort = sc.get('default_sort', 'relevance')
        search_flat = s_cfg.get('download', {}).get('extract_flat', {}).get('search', False)

        total_wanted = 30
        while True:
            print(f"Searching ({total_wanted} results)...")
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'extract_flat': search_flat}) as ydl:
                    results = ydl.extract_info(f"ytsearch{total_wanted}:{query}", download=False)
            except Exception as e:
                print(f"Search failed: {e}")
                sys.exit(1)
            entries = results.get('entries', [])
            if not entries:
                print("No results found")
                sys.exit(0)

            if filter_type == 'video':
                entries = [e for e in entries if not _is_pl(e)]
            elif filter_type == 'playlist':
                entries = [e for e in entries if _is_pl(e)]

            if default_sort == 'views':
                entries.sort(key=lambda e: e.get('view_count', 0) or 0, reverse=True)
            elif default_sort == 'date':
                entries.sort(key=lambda e: e.get('upload_date', '') or '', reverse=True)
            elif default_sort == 'duration':
                entries.sort(key=lambda e: e.get('duration', 0) or 0, reverse=True)

            if not entries:
                print("No matching results")
                sys.exit(0)

            try:
                from rich.table import Table
                from rich.console import Console
                console = Console()
                table = Table(title=f"Search results: {query}")
                table.add_column("#", style="dim", width=4)
                table.add_column("T", width=3)
                table.add_column("Title", ratio=3)
                table.add_column("Channel", ratio=2)
                table.add_column("Date", width=10)
                table.add_column("Duration", width=6)
                table.add_column("Views", width=8)
                for i, e in enumerate(entries, 1):
                    etype = '[P]' if _is_pl(e) else '[V]'
                    dur = int(e.get('duration', 0) or 0)
                    dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else '?'
                    views = e.get('view_count', 0) or 0
                    views_str = f"{views:,}" if views else '?'
                    rdate = _rel_date(e.get('upload_date', ''))
                    table.add_row(str(i), etype, e.get('title', '?')[:55], e.get('uploader', '?')[:22], rdate, dur_str, views_str)
                console.print(table)
            except ImportError:
                print("\nResults:")
                for i, e in enumerate(entries, 1):
                    tag = '[P]' if _is_pl(e) else '[V]'
                    print(f"  {i}. {tag} {e.get('title', '?')} - {e.get('uploader', '?')}")
                print(f"\nEnter numbers to download (e.g. 1,3,5-8), 'all' for all, 'more' for next {total_wanted}, or Enter to cancel:")
            print(f"\nEnter numbers to download (e.g. 1,3,5-8), 'all' for all, 'more' for next {total_wanted}, or Enter to cancel:")
            choice = input().strip().lower()
            if not choice:
                sys.exit(0)
            if choice == 'more':
                total_wanted += 30
                continue

            selected = []
            if choice == 'all':
                selected = [e['url'] if e.get('url') else f"https://www.youtube.com/watch?v={e['id']}" for e in entries if e]
            else:
                parts = choice.replace(',', ' ').split()
                for part in parts:
                    if '-' in part:
                        try:
                            a, b = part.split('-')
                            for idx in range(int(a), int(b) + 1):
                                if 1 <= idx <= len(entries):
                                    e = entries[idx - 1]
                                    selected.append(e['url'] if e.get('url') else f"https://www.youtube.com/watch?v={e['id']}")
                        except ValueError:
                            pass
                    else:
                        try:
                            idx = int(part)
                            if 1 <= idx <= len(entries):
                                e = entries[idx - 1]
                                selected.append(e['url'] if e.get('url') else f"https://www.youtube.com/watch?v={e['id']}")
                        except ValueError:
                            pass

            if not selected:
                print("No valid selections")
                sys.exit(0)

            print(f"Selected {len(selected)} result(s)")
            from utils.config import Config as SConfig
            from utils.logger import Logger as SLogger
            from utils.archive import Archive
            from utils.failed import FailedTracker
            from utils.skipped import SkippedTracker
            from utils.cli import CLI
            from mother_script import MotherScript
            s_cfg = SConfig()
            s_log = SLogger(s_cfg.resolve_path(s_cfg['general']['log_file']))
            s_ms = MotherScript(
                s_cfg, s_log,
                Archive(s_cfg.resolve_path(s_cfg['general']['archive_file'])),
                FailedTracker(s_cfg.resolve_path(s_cfg['general']['failed_file'])),
                SkippedTracker(s_cfg.resolve_path(s_cfg['general']['skipped_file'])),
                CLI(s_cfg)
            )
            s_ms.batch_download(' '.join(selected), s_cfg['general']['default_format'],
                                s_cfg['general']['downloads_dir'])
            sys.exit(0)

    if len(sys.argv) >= 2 and sys.argv[1] == 'watch':
        from utils.config import Config as WConfig
        from utils.logger import Logger as WLogger
        from utils.watcher import FolderWatcher
        from utils.archive import Archive
        from utils.failed import FailedTracker
        from utils.skipped import SkippedTracker
        from utils.cli import CLI
        from mother_script import MotherScript
        w_cfg = WConfig()
        w_log = WLogger(w_cfg.resolve_path(w_cfg['general']['log_file']))
        w = FolderWatcher(w_cfg, w_log, lambda: MotherScript(
            WConfig(), WLogger(w_cfg.resolve_path(w_cfg['general']['log_file'])),
            Archive(w_cfg.resolve_path(w_cfg['general']['archive_file'])),
            FailedTracker(w_cfg.resolve_path(w_cfg['general']['failed_file'])),
            SkippedTracker(w_cfg.resolve_path(w_cfg['general']['skipped_file'])),
            CLI(w_cfg)
        ))
        w.run()
        sys.exit(0)

    if len(sys.argv) >= 2 and sys.argv[1] in ('dashboard', 'dash', 'tui'):
        from utils.config import Config as DConfig
        from utils.logger import Logger as DLogger
        from utils.tui import run_dashboard
        run_dashboard(DConfig(), DLogger(''))
        sys.exit(0)

    if len(sys.argv) >= 2 and sys.argv[1] == 'schedule':
        from utils.config import Config as SchConfig
        from utils.logger import Logger as SchLogger
        from utils.archive import Archive
        from utils.failed import FailedTracker
        from utils.skipped import SkippedTracker
        from utils.cli import CLI
        from mother_script import MotherScript
        from utils.scheduler import Scheduler
        sch_cfg = SchConfig()
        sch_log = SchLogger(sch_cfg.resolve_path(sch_cfg['general']['log_file']))
        sch = Scheduler(sch_cfg, sch_log)
        cmd_args = sys.argv[2:]
        if not cmd_args or cmd_args[0] in ('help', '-h', '--help'):
            print("Usage: melt schedule <add|list|remove|daemon> [args]")
            print("  add <url>       Add a scheduled download")
            print("    --interval N    Run every N hours")
            print("    --at HH:MM      Run at specific time daily")
            print("    --fmt FMT       Format (video/audio/both)")
            print("    --dest PATH     Download destination")
            print("  list             List all scheduled jobs")
            print("  remove <id>      Remove a scheduled job")
            print("  daemon          Run as scheduler daemon")
            sys.exit(0)
        action = cmd_args[0]
        if action == 'list':
            jobs = sch.list()
            if not jobs:
                print("No scheduled jobs")
            else:
                for j in jobs:
                    enabled = 'enabled' if j.get('enabled', True) else 'disabled'
                    next_dt = j.get('next_run', 'never')
                    last_dt = j.get('last_run', 'never')
                    print(f"  [{j['id']}] {enabled} | {j['url'][:60]} | next: {next_dt}")
            sys.exit(0)
        if action == 'remove':
            if len(cmd_args) < 2:
                print("Usage: melt schedule remove <id>")
                sys.exit(1)
            if sch.remove(cmd_args[1]):
                print(f"Removed job {cmd_args[1]}")
            else:
                print(f"Job {cmd_args[1]} not found")
            sys.exit(0)
        if action == 'add':
            if len(cmd_args) < 2:
                print("Usage: melt schedule add <url> [--interval N] [--at HH:MM] [--fmt FMT] [--dest PATH]")
                sys.exit(1)
            url = cmd_args[1]
            interval = 0
            at_time = ''
            fmt = 'video'
            dest = sch_cfg['general']['downloads_dir']
            i = 2
            while i < len(cmd_args):
                if cmd_args[i] == '--interval' and i + 1 < len(cmd_args):
                    interval = int(cmd_args[i + 1])
                    i += 2
                elif cmd_args[i] == '--at' and i + 1 < len(cmd_args):
                    at_time = cmd_args[i + 1]
                    i += 2
                elif cmd_args[i] == '--fmt' and i + 1 < len(cmd_args):
                    fmt = cmd_args[i + 1]
                    i += 2
                elif cmd_args[i] == '--dest' and i + 1 < len(cmd_args):
                    dest = cmd_args[i + 1]
                    i += 2
                else:
                    i += 1
            job_id = sch.add(url, interval, at_time, fmt, dest)
            print(f"Scheduled job {job_id} added")
            sys.exit(0)
        if action == 'daemon':
            print("MelT scheduler daemon started (Ctrl+C to stop)")
            sch_log.info("Scheduler daemon started")
            while True:
                try:
                    ran = sch.run_due(lambda: MotherScript(
                        SchConfig(), SchLogger(sch_cfg.resolve_path(sch_cfg['general']['log_file'])),
                        Archive(sch_cfg.resolve_path(sch_cfg['general']['archive_file'])),
                        FailedTracker(sch_cfg.resolve_path(sch_cfg['general']['failed_file'])),
                        SkippedTracker(sch_cfg.resolve_path(sch_cfg['general']['skipped_file'])),
                        CLI(sch_cfg)
                    ))
                    if ran:
                        sch_log.info("Scheduler: jobs executed")
                except Exception as e:
                    sch_log.error(f"Scheduler error: {e}")
                time.sleep(60)
            sys.exit(0)
        print(f"Unknown schedule action: {action}")
        sys.exit(1)

    if len(sys.argv) >= 2 and sys.argv[1] in ('export', 'import'):
        action = sys.argv[1]
        if len(sys.argv) < 3:
            print(f"Usage: python main.py {action} <file>")
            sys.exit(1)
        filepath = sys.argv[2]
        if action == 'export':
            print("Enter URLs (one per line, empty line to finish):")
            urls = []
            while True:
                line = input().strip()
                if not line:
                    break
                urls.append(line)
            if not urls:
                print("No URLs to export")
                sys.exit(0)
            from utils.config import Config
            zcfg = Config()
            data = {
                "version": 1,
                "urls": urls,
                "fmt": zcfg['general'].get('default_format', 'video'),
                "dest": zcfg['general'].get('downloads_dir', 'downloads'),
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"Exported {len(urls)} URL(s) to {filepath}")
            sys.exit(0)
        if action == 'import':
            if not os.path.exists(filepath):
                print(f"ERROR: {filepath} not found")
                sys.exit(1)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            urls = data.get('urls', [])
            if not urls:
                print("No URLs in queue file")
                sys.exit(0)
            print(f"Imported {len(urls)} URL(s) from {filepath}")
            import tempfile
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
            for u in urls:
                tmp.write(u + '\n')
            tmp.close()
            sys.argv = [sys.argv[0], f'@{tmp.name}']

    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        print("ERROR: ffmpeg not found.")
        print("  The standalone .exe bundles ffmpeg automatically.")
        print("  If running from source, install ffmpeg:")
        print("    Windows: scoop install ffmpeg")
        print("    macOS:   brew install ffmpeg")
        print("    Linux:   sudo apt install ffmpeg")
        print("    Termux:  pkg install ffmpeg")
        input("\nPress Enter to exit...")
        sys.exit(1)

    if _is_bundled():
        os.environ['FFMPEG_PATH'] = ffmpeg_path

    if not check_nodejs():
        os.environ['YTDLP_NO_NODE'] = '1'

    try:
        import importlib.util
        for mod in ('rich', 'yt_dlp'):
            if importlib.util.find_spec(mod) is None:
                raise ImportError(mod)
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("If running from source: pip install -r requirements.txt")
        input("\nPress Enter to exit...")
        sys.exit(1)

    from utils.config import Config
    from utils.logger import Logger
    from utils.archive import Archive
    from utils.failed import FailedTracker
    from utils.skipped import SkippedTracker
    from utils.cli import CLI
    from mother_script import MotherScript

    if profile_name:
        from utils.config import _working_dir
        cfg_base = Config()
        profile_path = os.path.join(os.path.dirname(cfg_base.config_path), 'profiles', f"{profile_name}.json")
        if not os.path.exists(profile_path):
            print(f"ERROR: Profile '{profile_name}' not found at {profile_path}")
            sys.exit(1)
        config = Config(profile_path)
    else:
        config = Config()

    errors = config.validate()
    if errors:
        print("ERROR: Invalid configuration:")
        for e in errors:
            print(f"  - {e}")
        print("Fix config/config.json or delete it to regenerate defaults.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    log_path = config.resolve_path(config['paths']['log_file'])
    archive_path = config.resolve_path(config['paths']['archive_file'])
    failed_path = config.resolve_path(config['paths']['failed_file'])
    skipped_path = config.resolve_path(config['paths']['skipped_file'])

    logger = Logger(log_path)
    archive = Archive(archive_path)
    failed = FailedTracker(failed_path)
    skipped = SkippedTracker(skipped_path)
    cli = CLI(config)

    logger.info("MelT started")

    try:
        mother = MotherScript(config, logger, archive, failed, skipped, cli)
        mother.run(resume)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting.")
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\nFatal error: {e}")
        if config['general'].get('enable_sounds', True):
            from utils.notification import notify_async as _nfy
            _nfy("Fatal Error", f"{e}", "fatal_error", config=config)

    logger.info("MelT finished")

    if _is_bundled():
        input("\nPress Enter to exit...")


if __name__ == '__main__':
    main()
