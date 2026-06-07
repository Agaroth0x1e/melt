import os
import json
import shutil
import re
import sys
import time
from datetime import datetime
import signal
import atexit
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.table import Table
from rich import box

from components.downloader import Downloader
from components.subcleaner import SubCleaner
from components.remuxer import Remuxer
from utils.notification import notify_async as _notify
from utils.stats import StatsTracker
from utils.transliterate import Transliterator
from utils.warp import WarpManager


class MotherScript:
    def __init__(self, config, logger, archive, failed, skipped, cli):
        self.config = config
        self.logger = logger
        self.archive = archive
        self.failed = failed
        self.skipped = skipped
        self.cli = cli
        self.downloader = Downloader(config, logger)
        self.subcleaner = SubCleaner(logger)
        self.remuxer = Remuxer(logger)
        self.success_count = 0
        self.fail_count = 0
        self.sub_fail_count = 0
        self._temp_abs = None
        self._interrupted = False
        self._queue_lock = threading.Lock()

        self._sounds_enabled = self.config['general'].get('enable_sounds', True)
        self._prev_settings = None
        self.stats = StatsTracker(config)
        self.transliterator = Transliterator()
        self._warp_manager = None
        signal.signal(signal.SIGINT, self._handle_sigint)
        atexit.register(self._cleanup_temp)

    QUEUE_FILE = '_resume_queue.json'

    HELP_URL_TEXT = """
  [bold cyan]Inline Help[/]

  [bold]Basic usage:[/]
    Paste one or more YouTube URLs (space-separated) and press Enter.
    Use [bold]@file.txt[/] to load URLs from a batch text file.
    Type [bold]help[/] at any time to see this screen.

  [bold]Format selection:[/]
    [green]1[/]  Video (mp4) — downloads best video + audio, embeds thumbnails
    [green]2[/]  Audio (m4a) — downloads best audio, embeds thumbnail + lyrics
    [green]3[/]  Both — downloads video AND audio in parallel, auto-sorted to
              downloads/videos/ and downloads/audio/

  [bold]During prompts:[/]
    [green]Enter[/]              Accept default / auto-confirm
    [green]m[/]                  Modify options before starting (format, dest, etc.)
    [green]q[/] / [green]exit[/] / [green]quit[/]  Exit at most prompts

  [bold]Modify options (press [green]m[/]):[/]
    Items              Change URLs
    Format             video | audio | both
    Destination        Output folder
    Numbering          Yes / No (toggle)
    On Duplicate       skip | overwrite | keep
    Archive Action     skip | ask | redownload
    Dry Run            Yes / No (toggle)

  [bold]Session-persistent options:[/]
    After first download, MelT remembers your settings and offers
    to reuse them for the next batch. Choose:
      [green]Y[/]  Use same settings again
      [green]n[/]  Start fresh with new prompts
      [green]m[/]  Modify specific settings
      [green]s[/]  Show current settings
      [green]q[/]  Quit

  [bold]Playlists:[/]
    MelT auto-detects playlists and asks for a range (e.g. 1-5, 3,7-10)
    or type "all" for the full playlist. Range is asked fresh each time.
    Playlists create a subfolder using [bold]playlist_folder_template[/].
    New videos since last download are shown as [green]+ N new[/].

  [bold]Format preview:[/]
    When [bold]format_preview: true[/] in config, MelT shows a table of
    available formats before downloading. Pick a format ID to override
    auto-selection, or press Enter to let yt-dlp decide.

  [bold]Merge mode:[/]
    When [bold]merge_mode: true[/] in config, video and audio streams are
    downloaded separately then merged with MelT's own ffmpeg call.
    Useful when yt-dlp's internal merge fails on certain videos.

  [bold]Chapter splitter:[/]
    When [bold]chapter_splitter.enabled: true[/], downloaded videos with
    chapters are automatically split into per-chapter files after download.
    Named as: "[Title] - [Chapter Name].mp4". Original file is kept.

  [bold]Dry-run mode:[/]
    When enabled, MelT inspects all URLs and shows what would be downloaded
    without actually downloading anything. Useful for testing.

  [bold]Subtitles:[/]
    Set [bold]language[/] in config to download subtitles (default: [green]"en"[/]).
    Use comma-separated codes for multiple languages: [green]"en,ja,es"[/].
    Each language becomes a separate subtitle track in the output file.

    Available language codes:
      [green]ar[/] Arabic      [green]da[/] Danish      [green]de[/] German
      [green]el[/] Greek       [green]en[/] English      [green]es[/] Spanish
      [green]fi[/] Finnish     [green]fr[/] French       [green]he[/] Hebrew
      [green]hi[/] Hindi       [green]hu[/] Hungarian    [green]id[/] Indonesian
      [green]it[/] Italian     [green]ja[/] Japanese     [green]ko[/] Korean
      [green]nl[/] Dutch       [green]no[/] Norwegian    [green]pl[/] Polish
      [green]pt[/] Portuguese  [green]ro[/] Romanian     [green]ru[/] Russian
      [green]sv[/] Swedish     [green]th[/] Thai         [green]tr[/] Turkish
      [green]uk[/] Ukrainian   [green]vi[/] Vietnamese   [green]zh-Hans[/] Chinese (Simplified)
      [green]zh-Hant[/] Chinese (Traditional)

  [bold]Transliteration:[/]
    Set [bold]transliterate: "romaji"[/] in config to convert non-Latin scripts
    (Korean, Japanese, Chinese, Russian, Arabic, etc.) to romanized text.
    Default [green]""[/] keeps the original script.

  [bold]Subtitle processing:[/]
    [green]-[/] [music], [applause], [♪] and other bracketed annotations are stripped
    [green]-[/] Multi-line subtitle blocks are split into single karaoke-style lines
              with proportional timing for line-by-line display
    [green]-[/] Duplicate rolling captions are removed

  [bold]Keyboard shortcuts:[/]
    Ctrl+C       Abort current download batch immediately
    Enter        Confirm at prompts
    m            Modify settings
    q / quit     Quit

  [bold]WARP tunnel:[/]
    Set [bold]warp: true[/] in config to enable the built-in WARP tunnel
    via [bold]wireproxy[/] (userspace WireGuard — no admin rights needed).
    WARP routes through Cloudflare's nearest edge — great for avoiding
    YouTube 429 errors. Egress country is determined by Cloudflare, not
    user-selectable on free tier. For region-unlock, set a proxy instead.
    Set [bold]warp_retries: 3[/] for connection retry count.
    Menu [bold]10[/] toggles tunnel on/off; [bold]11[/] shows net status.

  [bold]Config:[/]
    Edit [bold]config/config.json[/] for permanent defaults:
      format, threads, timeout, numbering, duplicate action, sounds,
      warp, warp_location, format_preview, merge_mode, chapter_splitter,
      cookies, rate_limit, etc.
    Use [bold]melt --profile <name>[/] to load a saved profile.
    Use [bold]melt profile save <name>[/] to save a profile.
"""

    def _save_queue(self, entries, fmt, threads, do_numbering, dup_action):
        data = {
            'entries': [{'id': e.get('id', ''), 'title': e.get('title', ''),
                          'url': e['url'],
                          'dest_abs': e.get('dest_abs', ''),
                          'playlist': e.get('playlist', ''),
                          'fmt': e.get('fmt', fmt), 'done': False} for e in entries],
            'fmt': fmt, 'threads': threads,
            'do_numbering': do_numbering, 'duplicate_action': dup_action,
        }
        path = self.config.resolve_path(self.QUEUE_FILE)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_queue(self):
        path = self.config.resolve_path(self.QUEUE_FILE)
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            return json.load(f)

    def _remove_queue(self):
        path = self.config.resolve_path(self.QUEUE_FILE)
        if os.path.exists(path):
            os.remove(path)

    def _update_queue_done(self, entry_id, entry_url=''):
        path = self.config.resolve_path(self.QUEUE_FILE)
        if not os.path.exists(path):
            return
        with self._queue_lock:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                for e in data['entries']:
                    if e['id'] and e['id'] == entry_id:
                        e['done'] = True
                        break
                    if not e['id'] and e['url'] == entry_url:
                        e['done'] = True
                        break
                with open(path, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

    def _resolve_batch_urls(self, raw):
        urls = []
        for token in raw.split():
            if token.startswith('@'):
                path = token[1:]
                if not os.path.exists(path):
                    alt = os.path.join(os.path.dirname(self.config.config_path), path)
                    if os.path.exists(alt):
                        path = alt
                if os.path.exists(path):
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith('#'):
                                    urls.append(line)
                        self.cli.show_info(f"Loaded {len(urls)} URL(s) from {token}")
                    except Exception as e:
                        self.cli.show_error(f"Failed to read {token}: {e}")
                else:
                    self.cli.show_error(f"Batch file not found: {token}")
            else:
                urls.append(token)
        return urls

    def _sanitize(self, name):
        return re.sub(r'[\\/*?:"<>|]', '', name).strip()

    def _clean_error(self, msg):
        return re.sub(r'\x1b\[[0-9;]*m', '', str(msg))

    def _handle_sigint(self, sig, frame):
        self.cli.console.print("\n[yellow]Aborting...[/]")
        self.logger.info("SIGINT received, aborting")
        if self._sounds_enabled:
            from utils.notification import play_sound as _playsound
            _playsound('aborting', config=self.config)
        os._exit(1)

    def _cleanup_temp(self):
        if not self.config['general'].get('clear_temp', True):
            return
        if self._temp_abs and os.path.exists(self._temp_abs):
            for item in os.listdir(self._temp_abs):
                item_path = os.path.join(self._temp_abs, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception:
                    pass

    def _ensure_warp(self):
        if self._warp_manager is None:
            config_dir = os.path.dirname(self.config.config_path)
            self._warp_manager = WarpManager(config_dir, self.logger)
        return self._warp_manager

    def _connect_warp(self, force=False):
        if not force and not self.config['network'].get('warp', False):
            return False
        wm = self._ensure_warp()
        retries = self.config['network'].get('warp_retries', 3)
        self.cli.show_info("Connecting WARP tunnel...")
        self.logger.info(f"Connecting WARP tunnel (retries={retries})...")
        ok = wm.connect(max_retries=retries, cli=self.cli)
        if ok:
            self.cli.console.print("  [green]Connected to tunnel[/]")
            self.logger.info("Tunnel connected")
        else:
            self.cli.console.print("  [red]Tunnel connection failed[/]")
            self.logger.info("Tunnel connection failed")
        return ok

    def _disconnect_warp(self):
        if self._warp_manager and self._warp_manager.is_connected():
            self.cli.show_info("Disconnecting WARP tunnel...")
            self._warp_manager.disconnect()

    def _run_download_flow(self):
        threads = self.config['download']['max_threads']
        do_numbering = self.config['download'].get('numbering', False)
        duplicate_action = self.config['download'].get('duplicate_action', 'skip')
        dry_run = False

        raw = ''
        while True:
            while True:
                if not raw:
                    raw = self.cli.ask_url()
                raw = raw.strip()
                if raw.lower() in ('exit', 'quit', 'q'):
                    self.logger.info("User exited from URL prompt")
                    return
                if raw.lower().startswith('menu') or raw.lower() in ('back', 'b'):
                    return
                if raw.lower() == 'help':
                    self.cli.console.print(self.HELP_URL_TEXT)
                    raw = ''
                    continue
                urls = self._resolve_batch_urls(raw)
                raw = ''
                if not urls:
                    continue

                self.logger.info(f"URLs entered: {urls[:5]}{'...' if len(urls) > 5 else ''} ({len(urls)} total)")
                if len(urls) > 1:
                    self.cli.show_info(f"Loaded {len(urls)} URL(s)")

                if self._prev_settings:
                    reuse = self.cli.ask_reuse_settings(self._prev_settings)
                    if reuse == 'exit':
                        return
                    if reuse in ('yes', 'modify'):
                        fmt = self._prev_settings['fmt']
                        dest = self._prev_settings['dest']
                        do_numbering = self._prev_settings['numbering']
                        duplicate_action = self._prev_settings['duplicate_action']
                        dry_run = self._prev_settings.get('dry_run', dry_run)
                        archive_action = self._prev_settings.get('archive_action', self.config['download'].get('archive_action', 'skip'))
                    else:
                        fmt = self.cli.ask_format()
                        dest = self.cli.ask_destination()
                else:
                    reuse = None
                    fmt = self.cli.ask_format()
                    dest = self.cli.ask_destination()
                self.logger.info(f"Options: fmt={fmt}, dest={dest}, numbering={do_numbering}, dup={duplicate_action}, dry_run={dry_run}")

                if dest == self.config['paths']['downloads_dir'] and fmt != 'both':
                    dest = os.path.join(dest, 'videos' if fmt == 'video' else 'audio')

                url_infos = []
                for url in urls:
                    short = url[:60]
                    self.cli.show_info(f"Analyzing {short}...")
                    try:
                        url_infos.append((url, self.downloader.inspect_url(url)))
                    except Exception as e:
                        self.cli.show_warning(f"Invalid URL: {url}")
                        self.logger.error(f"Failed to inspect {url}: {e}")

                if not url_infos:
                    self.cli.show_warning("No valid URLs provided")
                    raw = ''
                    continue

                from utils.rules import RuleManager
                rule_mgr = RuleManager(self.config, self.logger)
                rule_match = rule_mgr.match(url_infos[0][1]) if url_infos else None
                if rule_match:
                    if rule_match.get('fmt'):
                        fmt = rule_match['fmt']
                        self.cli.show_info(f"Rule matched: format set to {fmt}")
                    if rule_match.get('dest'):
                        dest = rule_match['dest']
                        self.cli.show_info(f"Rule matched: destination set to {dest}")

                if self._sounds_enabled:
                    _notify("Analysis Complete", f"{len(url_infos)} URL(s) inspected", "analyze_complete", config=self.config)

                all_entries = []
                def make_video_audio(entry_base, base_dest):
                    if fmt == 'both':
                        v = os.path.join(base_dest, 'videos') if base_dest == self.config['paths']['downloads_dir'] else base_dest
                        a = os.path.join(base_dest, 'audio') if base_dest == self.config['paths']['downloads_dir'] else base_dest
                        return [
                            {**entry_base, 'dest_abs': v, 'fmt': 'video'},
                            {**entry_base, 'dest_abs': a, 'fmt': 'audio'},
                        ]
                    return [{**entry_base, 'dest_abs': base_dest, 'fmt': fmt}]

                for url, info in url_infos:
                    if info['is_playlist']:
                        self.cli.show_info(f"Fetching playlist: \"{info['title']}\"...")
                        try:
                            entries, pl_title, pl_id = self.downloader.get_playlist_entries(url)
                        except Exception as e:
                            self.cli.show_error(f"Failed to expand playlist {url}: {e}")
                            self.logger.error(f"Failed to expand playlist {url}: {e}")
                            continue

                        if self.config['download'].get('reverse_playlist', False):
                            entries = list(reversed(entries))

                        snapshot = self._load_playlist_snapshot(pl_id)
                        if snapshot:
                            self._show_playlist_diff(snapshot.get('videos', []), entries, pl_title)
                        self._save_playlist_snapshot(pl_id, pl_title, entries)

                        prange = self.cli.ask_playlist_range(len(entries), identifier=pl_title)
                        if prange.lower() != 'all':
                            entries = self._parse_range(prange, entries)

                        tmpl = self.config['download'].get('playlist_folder_template', '%(playlist_title)s')
                        folder = tmpl.replace('%(playlist_title)s', pl_title).replace('%(playlist_id)s', pl_id)
                        safe_folder = self._sanitize(folder)
                        pl_dest = dest if os.path.isabs(dest) else self.config.resolve_path(dest)
                        pl_dest = os.path.join(pl_dest, safe_folder)

                        for e in entries:
                            all_entries.extend(make_video_audio(e, pl_dest))
                    else:
                        all_entries.extend(make_video_audio(
                            {'url': url, 'id': info['id'], 'title': info['title']}, dest
                        ))

                archive_action = self.config['download'].get('archive_action', 'skip')
                if self._prev_settings:
                    archive_action = self._prev_settings.get('archive_action', archive_action)

                options = self._build_options(all_entries, fmt, dest, do_numbering, duplicate_action, dry_run, archive_action)
                self.cli.show_options_summary(options)

                timeout = self.config['network']['timeout_seconds']
                mod_key = None
                _force_modify = (reuse == 'modify') if self._prev_settings else False
                while True:
                    action = self.cli.show_start_prompt(timeout, force_modify=_force_modify)
                    _force_modify = False
                    if action in ('start', ''):
                        self.logger.info("User started download")
                        break
                    if action.lower() == 'm':
                        mod_key = self.cli.ask_modify_option(options)
                        if mod_key is None:
                            break
                        if mod_key == 'Items':
                            self.cli.show_info("Enter new URL(s):")
                            break
                        new_val = self._modify_option(mod_key, fmt, dest, do_numbering, duplicate_action, dry_run, archive_action)
                        if new_val is not None:
                            self.logger.info(f"Modify: {mod_key} -> {new_val}")
                            if mod_key == 'Format':
                                fmt = new_val
                            elif mod_key == 'Destination':
                                dest = new_val
                            elif mod_key == 'Numbering':
                                do_numbering = new_val
                            elif mod_key == 'On Duplicate':
                                duplicate_action = new_val
                            elif mod_key == 'Archive Action':
                                archive_action = new_val
                            elif mod_key == 'Dry Run':
                                dry_run = new_val
                        continue
                    self.cli.show_warning("Invalid option. Press Enter to start or type 'm' to modify.")
                if action in ('start', ''):
                    break
                if mod_key == 'URLs':
                    continue
                break

            if self.config['download'].get('format_preview', False) and not any(e.get('chosen_format') for e in all_entries):
                unique_urls = list(dict.fromkeys(e['url'] for e in all_entries))
                for u in unique_urls[:1]:
                    try:
                        fmts = self.downloader.fetch_formats(u)
                        if fmts:
                            chosen = self.cli.show_format_preview(all_entries[0].get('title', u), fmts)
                            self.logger.info(f"Format preview: user selected format ID {chosen}" if chosen else "Format preview: user skipped selection")
                            if chosen:
                                for e in all_entries:
                                    e['chosen_format'] = chosen
                    except Exception:
                        self.cli.show_warning("Could not fetch format preview")

            self._execute_all(all_entries, fmt, threads, do_numbering, duplicate_action, dry_run, archive_action=archive_action)

            self._save_prev_settings(fmt, dest, do_numbering, duplicate_action, dry_run, archive_action)

            if self.config['general'].get('exit_on_complete', False):
                break

            answer = self.cli.ask_continue()
            self.logger.info(f"Continue choice: {answer}")
            if answer.lower() in ('exit', 'quit', 'q'):
                break
            if answer.lower().startswith('menu') or answer.lower() in ('back', 'b'):
                return
            raw = answer

    def run(self, resume=False):
        if not resume:
            self.cli.show_banner()

        if resume:
            queue = self._load_queue()
            if not queue:
                self.cli.show_error("No resume queue found")
                return
            fmt = queue['fmt']
            threads = queue.get('threads', self.config['download']['max_threads'])
            do_numbering = queue.get('do_numbering', False)
            duplicate_action = queue.get('duplicate_action', 'skip')
            pending = [e for e in queue['entries'] if not e['done']]
            done_count = sum(1 for e in queue['entries'] if e['done'])
            self.cli.show_info(f"Resuming queue: {len(pending)} pending, {done_count} completed")
            if not pending:
                self.cli.show_info("All items already completed")
                self._remove_queue()
                return
            self._execute_all(pending, fmt, threads, do_numbering, duplicate_action, resume=resume)
            return

        first = True
        while True:
            choice = self.cli.show_main_menu(show_table=first)
            first = False
            self.logger.info(f"Menu choice: {choice}")

            if choice == '1':
                self._run_download_flow()
                continue

            elif choice == '2':
                query = self.cli.timed_input("[bold yellow]Search YouTube:[/] ")
                if not query:
                    continue
                self.logger.info(f"Search query: {query}")
                self._run_search(query)
                continue

            elif choice in ('3', 'analytics'):
                self.logger.info("Viewing analytics")
                self._run_analytics()
                continue

            elif choice in ('4', 'dashboard'):
                self.logger.info("Opening dashboard")
                self._run_dashboard()
                continue

            elif choice == '5':
                self.logger.info("Schedule menu")
                self._run_schedule_menu()
                continue

            elif choice == '6':
                self.logger.info("Rules menu")
                self._run_rules_menu()
                continue

            elif choice == '7':
                self.logger.info("Starting watch folder")
                self._run_watch()
                continue

            elif choice == '8':
                self.logger.info("Sync menu")
                self._run_sync_menu()
                continue

            elif choice in ('9', 'help'):
                self.logger.info("Viewed inline help")
                self.cli.console.print(self.HELP_URL_TEXT)
                continue

            elif choice in ('11', 'net'):
                self.logger.info("Check net status")
                wm = self._ensure_warp()
                wm.show_status(self.cli)
                self.cli.press_enter()
                continue

            elif choice in ('10', 'tunnel'):
                if not self.config['network'].get('warp', False):
                    self.cli.console.print("  [red]WARP is not enabled.[/] Turn it on in config ([green]warp: true[/]).")
                    self.cli.press_enter()
                    continue
                wm = self._ensure_warp()
                if wm.is_connected():
                    self._disconnect_warp()
                    self.cli.show_info("Disconnected from tunnel")
                    self.logger.info("Tunnel disconnected")
                else:
                    self._connect_warp(force=True)
                self.cli.press_enter()
                continue

            elif choice in ('q', 'quit', 'exit', '0'):
                self.logger.info("User exited")
                self.cli.show_info("Goodbye!")
                break

    @staticmethod
    def _rel_date(ud):
        if not ud:
            return ''
        try:
            if isinstance(ud, (int, float)):
                d = datetime.fromtimestamp(ud)
            else:
                d = datetime.strptime(str(ud), '%Y%m%d')
            diff = datetime.now() - d
            days = diff.days
            if days < 1:
                return 'today'
            if days == 1:
                return 'yesterday'
            if days < 7:
                return f'{days}d ago'
            if days < 30:
                return f'{days // 7}w ago'
            if days < 365:
                return f'{days // 30}mo ago'
            return f'{days // 365}y ago'
        except Exception:
            return ''

    def _run_search(self, query):
        import yt_dlp
        self.cli.show_info(f"Searching for: {query}")

        sc = self.config.get('search', {})
        filter_type = sc.get('filter_type', 'all')
        default_sort = sc.get('default_sort', 'relevance')

        def _is_playlist_entry(e):
            ie = e.get('ie_key', '')
            url = e.get('url', '')
            return ie == 'YoutubePlaylist' or 'playlist?list=' in url or '/playlist?' in url

        search_flat = self.config.get('download', {}).get('extract_flat', {}).get('search', False)
        total_wanted = 30
        while True:
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'extract_flat': search_flat}) as ydl:
                    results = ydl.extract_info(f"ytsearch{total_wanted}:{query}", download=False)
            except Exception as e:
                self.cli.show_error(f"Search failed: {e}")
                return
            entries = results.get('entries', [])
            if not entries:
                self.cli.show_warning("No results found")
                return

            if filter_type == 'video':
                entries = [e for e in entries if not _is_playlist_entry(e)]
            elif filter_type == 'playlist':
                entries = [e for e in entries if _is_playlist_entry(e)]

            if default_sort == 'views':
                entries.sort(key=lambda e: e.get('view_count', 0) or 0, reverse=True)
            elif default_sort == 'date':
                entries.sort(key=lambda e: e.get('upload_date', '') or '', reverse=True)
            elif default_sort == 'duration':
                entries.sort(key=lambda e: e.get('duration', 0) or 0, reverse=True)

            if not entries:
                self.cli.show_warning("No matching results")
                return

            from rich.table import Table
            table = Table(title=f"Search results: {query}", box=None)
            table.add_column("#", style="dim", width=4)
            table.add_column("Type", width=4)
            table.add_column("Title", ratio=3)
            table.add_column("Channel", ratio=2)
            table.add_column("Date", width=10)
            table.add_column("Duration", width=6)
            table.add_column("Views", width=8)
            for i, e in enumerate(entries, 1):
                etype = '[P]' if _is_playlist_entry(e) else '[V]'
                dur = int(e.get('duration', 0) or 0)
                dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else '?'
                views = e.get('view_count', 0) or 0
                views_str = f"{views:,}" if views else '?'
                rdate = self._rel_date(e.get('upload_date', ''))
                table.add_row(str(i), etype, e.get('title', '?')[:55], e.get('uploader', '?')[:22], rdate, dur_str, views_str)
            self.cli.console.print(table)

            choice = self.cli.timed_input(f"\n[bold yellow]Enter numbers to download[/] [dim](e.g. 1,3,5-8)[/], [bold]'all'[/] for all, [bold]'more'[/] for next {total_wanted}, or [bold]Enter[/] to cancel: ").lower()
            if not choice:
                return
            if choice == 'more':
                total_wanted += 30
                continue

            selected_urls = []
            if choice == 'all':
                selected_urls = [e['url'] if e.get('url') else f"https://www.youtube.com/watch?v={e['id']}" for e in entries if e]
            else:
                parts = choice.replace(',', ' ').split()
                for part in parts:
                    if '-' in part:
                        try:
                            a, b = part.split('-')
                            for idx in range(int(a), int(b) + 1):
                                if 1 <= idx <= len(entries):
                                    e = entries[idx - 1]
                                    selected_urls.append(e['url'] if e.get('url') else f"https://www.youtube.com/watch?v={e['id']}")
                        except ValueError:
                            pass
                    else:
                        try:
                            idx = int(part)
                            if 1 <= idx <= len(entries):
                                e = entries[idx - 1]
                                selected_urls.append(e['url'] if e.get('url') else f"https://www.youtube.com/watch?v={e['id']}")
                        except ValueError:
                            pass
            if not selected_urls:
                self.cli.show_warning("No valid selections")
                return
            self.logger.info(f"Search selected {len(selected_urls)} result(s): {selected_urls[:3]}...")
            self.cli.show_info(f"Selected {len(selected_urls)} result(s)")
            self.batch_download(' '.join(selected_urls), self.config['download']['default_format'],
                                self.config['paths']['downloads_dir'])
            return

    def _run_analytics(self):
        from utils.stats import show_analytics
        show_analytics(self.config.resolve_path(os.path.join('logs', 'stats.json')))
        self.cli.press_enter("Press Enter to return to menu...")

    def _run_dashboard(self):
        from utils.tui import run_dashboard
        run_dashboard(self.config, self.logger)

    def _run_schedule_menu(self):
        from utils.scheduler import Scheduler
        sch = Scheduler(self.config, self.logger)
        while True:
            s_choice = self.cli.show_schedule_menu()
            self.logger.info(f"Schedule menu choice: {s_choice}")
            if s_choice == '1':
                jobs = sch.list()
                if not jobs:
                    self.cli.show_info("No scheduled jobs")
                else:
                    for j in jobs:
                        enabled = 'enabled' if j.get('enabled', True) else 'disabled'
                        next_dt = j.get('next_run', 'never')
                        last_dt = j.get('last_run', 'never')
                        self.cli.console.print(f"  [{j['id']}] {enabled} | {j['url'][:60]} | next: {next_dt}")
                self.cli.press_enter("Press Enter...")
            elif s_choice == '2':
                url = self.cli.timed_input("[bold]URL[/]: ")
                if not url:
                    continue
                interval = self.cli.timed_input("[bold]Interval in hours[/] (0 for one-time): ", '0')
                interval = int(interval) if interval.isdigit() else 0
                fmt = self.cli.timed_input("[bold]Format[/] (video/audio/both) [default: video]: ", 'video')
                dest = self.cli.timed_input("[bold]Destination[/] [default: downloads]: ", 'downloads')
                jid = sch.add(url, interval, '', fmt, dest)
                self.logger.info(f"Schedule job added: {jid} -> {url[:60]}, every {interval}h, fmt={fmt}")
                self.cli.show_info(f"Scheduled job {jid} added")
            elif s_choice == '3':
                jid = self.cli.timed_input("[bold]Job ID to remove[/]: ")
                if sch.remove(jid):
                    self.logger.info(f"Schedule job removed: {jid}")
                    self.cli.show_info(f"Removed job {jid}")
                else:
                    self.cli.show_error(f"Job {jid} not found")
            elif s_choice == '4':
                self.logger.info("Starting scheduler daemon")
                self.cli.show_info("Starting scheduler daemon (Ctrl+C to stop)...")
                try:
                    while True:
                        due = sch.due_jobs()
                        for job in due:
                            self.cli.show_info(f"Running scheduled job {job['id']}: {job['url'][:50]}")
                            self.batch_download(job['url'], job.get('fmt', 'video'), job.get('dest', 'downloads'))
                            sch.mark_run(job['id'])
                        import time as t
                        t.sleep(60)
                except KeyboardInterrupt:
                    self.logger.info("Scheduler daemon stopped")
            elif s_choice in ('b', 'back', 'q', 'quit'):
                break

    def _run_rules_menu(self):
        from utils.rules import RuleManager
        rm = RuleManager(self.config, self.logger)
        while True:
            r_choice = self.cli.show_rules_menu()
            self.logger.info(f"Rules menu choice: {r_choice}")
            if r_choice == '1':
                rules = rm.list()
                if not rules:
                    self.cli.show_info("No rules defined")
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
                        self.cli.console.print(f"  [{r['id']}] {', '.join(desc)} -> {', '.join(a_desc)}")
                self.cli.press_enter("Press Enter...")
            elif r_choice == '2':
                match = {}
                action = {}
                kw = self.cli.timed_input("[bold]Keyword to match[/] (or Enter to skip): ")
                if kw: match['keyword'] = kw
                ch = self.cli.timed_input("[bold]Channel name to match[/] (or Enter to skip): ")
                if ch: match['channel'] = ch
                urlp = self.cli.timed_input("[bold]URL pattern to match[/] (or Enter to skip): ")
                if urlp: match['url_pattern'] = urlp
                if not match:
                    self.cli.show_warning("At least one match criteria required")
                    continue
                fmt = self.cli.timed_input("[bold]Format to apply[/] (video/audio/both) [Enter to skip]: ")
                if fmt: action['fmt'] = fmt
                dest = self.cli.timed_input("[bold]Destination to apply[/] [Enter to skip]: ")
                if dest: action['dest'] = dest
                rid = rm.add(match, action)
                self.logger.info(f"Rule added: {rid} -> match={match}, action={action}")
                self.cli.show_info(f"Rule {rid} added")
            elif r_choice == '3':
                rid = self.cli.timed_input("[bold]Rule ID to remove[/]: ")
                if rm.remove(rid):
                    self.logger.info(f"Rule removed: {rid}")
                    self.cli.show_info(f"Rule {rid} removed")
                else:
                    self.cli.show_error(f"Rule {rid} not found")
            elif r_choice in ('b', 'back', 'q', 'quit'):
                break

    def _run_watch(self):
        from utils.watcher import FolderWatcher
        w = FolderWatcher(self.config, self.logger, lambda: self)
        w.run()

    def _run_sync_menu(self):
        from utils.sync import SyncManager
        sm = SyncManager(self.config, self.logger)
        while True:
            sy_choice = self.cli.show_sync_menu()
            self.logger.info(f"Sync menu choice: {sy_choice}")
            if sy_choice == '1':
                remote = self.cli.timed_input("[bold]Remote URL[/] (or Enter for local only): ")
                result = sm.init(remote)
                self.logger.info(f"Sync init: {result}")
                self.cli.console.print(result)
                self.cli.press_enter("Press Enter...")
            elif sy_choice == '2':
                msg = self.cli.timed_input("[bold]Commit message[/] [Enter for auto]: ")
                result = sm.push(msg)
                self.logger.info(f"Sync push: {result}")
                self.cli.console.print(result)
                self.cli.press_enter("Press Enter...")
            elif sy_choice == '3':
                result = sm.pull()
                self.logger.info(f"Sync pull: {result}")
                self.cli.console.print(result)
                self.cli.press_enter("Press Enter...")
            elif sy_choice == '4':
                st = sm.status()
                rs = sm.remote_status()
                self.cli.console.print(st)
                self.cli.console.print()
                self.cli.console.print(rs)
                self.cli.press_enter("Press Enter...")
            elif sy_choice in ('b', 'back', 'q', 'quit'):
                break

    def batch_download(self, url, fmt, dest):
        threads = self.config['download']['max_threads']
        do_numbering = self.config['download'].get('numbering', False)
        duplicate_action = self.config['download'].get('duplicate_action', 'skip')
        dry_run = self.config['general'].get('dry_run', False)

        if dest == self.config['paths']['downloads_dir'] and fmt != 'both':
            dest = os.path.join(dest, 'videos' if fmt == 'video' else 'audio')

        urls = self._resolve_batch_urls(url)
        if not urls:
            self.logger.error("No valid URLs for scheduled job")
            return

        url_infos = []
        for u in urls:
            try:
                url_infos.append((u, self.downloader.inspect_url(u)))
            except Exception as e:
                self.logger.error(f"Failed to inspect {u}: {e}")

        all_entries = []
        def make_video_audio(entry_base, base_dest):
            entry_fmt = entry_base.get('fmt', fmt)
            if entry_fmt == 'both':
                v = os.path.join(base_dest, 'videos') if base_dest == self.config['paths']['downloads_dir'] else base_dest
                a = os.path.join(base_dest, 'audio') if base_dest == self.config['paths']['downloads_dir'] else base_dest
                return [
                    {**entry_base, 'dest_abs': v, 'fmt': 'video'},
                    {**entry_base, 'dest_abs': a, 'fmt': 'audio'},
                ]
            return [{**entry_base, 'dest_abs': base_dest, 'fmt': entry_fmt}]

        for u, info in url_infos:
            if info['is_playlist']:
                try:
                    entries, pl_title, pl_id = self.downloader.get_playlist_entries(u)
                except Exception as e:
                    self.logger.error(f"Failed to expand playlist {u}: {e}")
                    continue
                if self.config['download'].get('reverse_playlist', False):
                    entries = list(reversed(entries))
                tmpl = self.config['download'].get('playlist_folder_template', '%(playlist_title)s')
                folder = tmpl.replace('%(playlist_title)s', pl_title).replace('%(playlist_id)s', pl_id)
                safe_folder = self._sanitize(folder)
                pl_dest = os.path.join(dest, safe_folder)
                for e in entries:
                    all_entries.extend(make_video_audio(e, pl_dest))
            else:
                all_entries.extend(make_video_audio(
                    {'url': u, 'id': info['id'], 'title': info['title']}, dest
                ))

        self._execute_all(all_entries, fmt, threads, do_numbering, duplicate_action, dry_run)

    def _snapshot_path(self, pl_id):
        return self.config.resolve_path(os.path.join('logs', 'playlist_snapshots', f"{pl_id}.json"))

    def _load_playlist_snapshot(self, pl_id):
        path = self._snapshot_path(pl_id)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_playlist_snapshot(self, pl_id, pl_title, entries):
        path = self._snapshot_path(pl_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            'playlist_id': pl_id,
            'playlist_title': pl_title,
            'timestamp': datetime.now().isoformat(),
            'videos': [{'id': e.get('id', ''), 'title': e.get('title', ''), 'url': e.get('url', '')} for e in entries],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _show_playlist_diff(self, old_videos, new_videos, pl_title):
        old_ids = {v['id'] for v in old_videos if v.get('id')}
        new_ids = {v['id'] for v in new_videos if v.get('id')}
        added = [v for v in new_videos if v['id'] in new_ids - old_ids]
        removed = [v for v in old_videos if v['id'] in old_ids - new_ids]
        if not added and not removed:
            return None
        self.cli.console.print(f"\n[bold]Playlist changes:[/] {pl_title}")
        if added:
            self.cli.console.print(f"  [green]+ {len(added)} new[/]")
            for v in added[:5]:
                self.cli.console.print(f"    {v['title'][:60]}")
            if len(added) > 5:
                self.cli.console.print(f"    ... and {len(added)-5} more")
        if removed:
            self.cli.console.print(f"  [red]- {len(removed)} removed[/]")
            for v in removed[:5]:
                self.cli.console.print(f"    {v['title'][:60]}")
            if len(removed) > 5:
                self.cli.console.print(f"    ... and {len(removed)-5} more")
        return added

    def _save_prev_settings(self, fmt, dest, numbering, dup_action, dry_run, archive_action='skip'):
        self._prev_settings = {
            'fmt': fmt,
            'dest': dest,
            'numbering': numbering,
            'duplicate_action': dup_action,
            'dry_run': dry_run,
            'archive_action': archive_action,
        }

    def _parse_range(self, prange, entries):
        result = []
        for part in prange.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    a, b = part.split('-')
                    for i in range(int(a.strip()) - 1, min(int(b.strip()), len(entries))):
                        if 0 <= i < len(entries):
                            result.append(entries[i])
                except Exception:
                    pass
            else:
                try:
                    i = int(part) - 1
                    if 0 <= i < len(entries):
                        result.append(entries[i])
                except Exception:
                    pass
        return result if result else entries

    def _build_options(self, all_entries, fmt, dest, numbering, dup_action, dry_run=False, archive_action='skip'):
        n = len(all_entries)
        fmt_label = {'video': 'Video', 'audio': 'Audio', 'both': 'Both (Video + Audio)'}.get(fmt, fmt)
        if n <= 8:
            lines = [f"{n} item(s)"]
            for i, e in enumerate(all_entries, 1):
                title = e.get('title', e['url'])[:60]
                edest = e.get('dest_abs', dest)
                short = os.path.basename(edest) or edest
                efmt = e.get('fmt', '')
                fmt_tag = f" [{efmt}]" if efmt else ''
                lines.append(f"  #{i}: {title}  \u2192 {short}{fmt_tag}")
            items_str = '\n'.join(lines)
        else:
            groups = {}
            for e in all_entries:
                edest = e.get('dest_abs', dest)
                groups.setdefault(edest, 0)
                groups[edest] += 1
            summary_lines = [f"{n} item(s)"]
            for d, c in groups.items():
                short = os.path.basename(d) or d
                summary_lines.append(f"  {c} item(s) \u2192 {short}")
            items_str = '\n'.join(summary_lines)
        return {
            'Items': items_str,
            'Format': fmt_label,
            'Destination': dest,
            'Numbering': 'Yes' if numbering else 'No',
            'On Duplicate': dup_action,
            'Archive Action': archive_action.capitalize(),
            'Dry Run': 'Yes' if dry_run else 'No',
        }

    def _modify_option(self, key, fmt, dest, numbering, dup_action, dry_run=False, archive_action='skip'):
        if key == 'Format':
            return self.cli.ask_format()
        elif key == 'Destination':
            return self.cli.ask_destination()
        elif key == 'Numbering':
            return not numbering
        elif key == 'On Duplicate':
            return self.cli.ask_duplicate_action()
        elif key == 'Archive Action':
            return self.cli.ask_archive_action()
        elif key == 'Dry Run':
            return not dry_run
        return None

    def _show_dry_run(self, items, dests, fmt):
        table = Table(box=box.ROUNDED, title="[bold]Dry Run — Would Download[/]", title_justify="center")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Title", style="green")
        table.add_column("Type", style="yellow", width=6)
        table.add_column("Destination", style="white")
        for idx, (entry, num) in enumerate(items, 1):
            efmt = entry.get('fmt', fmt)
            typ = {"video": "Video", "audio": "Audio", "both": "Both"}.get(efmt, "?")
            dest_short = entry.get('dest_abs', '?').split('\\')[-1] or entry.get('dest_abs', '?')
            table.add_row(str(idx), entry.get('title', '?')[:50], typ, dest_short)
        self.cli.console.print(table)
        self.cli.console.print()

    def _execute_all(self, all_entries, fmt, threads, do_numbering, duplicate_action, dry_run=False, resume=False, archive_action='skip'):
        self.success_count = 0
        self.fail_count = 0
        self.sub_fail_count = 0
        self.skip_count = 0
        self._interrupted = False

        items = [(entry, idx + 1) for idx, entry in enumerate(all_entries)]
        if not items:
            return

        self._connect_warp()

        start_time = time.time()
        total = len(items)
        temp_abs = self.config.resolve_path(self.config['paths']['temp_dir'])
        self._temp_abs = temp_abs

        dests = set(e.get('dest_abs', '?') for e in all_entries)
        dest_label = ', '.join(dests) if len(dests) <= 3 else f"{len(dests)} destinations"

        if dry_run:
            self._show_dry_run(items, dests, fmt)
            return

        self.cli.show_info(f"Processing {total} item(s) with {threads} thread(s)")
        if self._sounds_enabled:
            _notify("Batch Started", f"Processing {total} item(s) \u2192 {dest_label}", "batch_start", config=self.config)

        if not resume:
            self._save_queue(all_entries, fmt, threads, do_numbering, duplicate_action)

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(
                    self._process_single, entry, idx, fmt, entry['dest_abs'], temp_abs,
                    do_numbering, duplicate_action, total, archive_action
                ): entry for entry, idx in items
            }

            done = 0
            for future in as_completed(futures):
                try:
                    entry = futures[future]
                    result = future.result()
                    if result == 'success':
                        self.success_count += 1
                    elif result == 'skip':
                        pass
                    else:
                        self.fail_count += 1
                    self._update_queue_done(entry.get('id', ''), entry.get('url', ''))
                except Exception as e:
                    entry = futures[future]
                    self.cli.show_error(f"{entry.get('title', entry.get('url', '?'))}: {e}")
                    self.fail_count += 1
                done += 1
                elapsed = time.time() - start_time
                m, s = divmod(int(elapsed), 60)
                sys.stderr.write(f'\rCompleted: {done}/{total}  Elapsed: {m}m{s:02d}s  ')
                sys.stderr.flush()
            if not self._interrupted:
                print()

        if not self._interrupted:
            self._remove_queue()

        log_file = self.config.resolve_path(self.config['paths']['log_file'])
        failed_file = self.config.resolve_path(self.config['paths']['failed_file'])
        skipped_file = self.config.resolve_path(self.config['paths']['skipped_file'])
        elapsed = time.time() - start_time
        dest_show = list(dests)[0] if len(dests) == 1 else dest_label
        self.cli.show_completion(self.success_count, self.fail_count, dest_show, log_file, failed_file, self.sub_fail_count, elapsed, self.skip_count, skipped_file)

        if self._sounds_enabled:
            if self.fail_count > 0 or self.sub_fail_count > 0:
                _notify("MelT Complete", f"{self.success_count} done, {self.fail_count} failed, {self.sub_fail_count} sub issues", "completion", config=self.config)
            else:
                _notify("MelT Complete", f"All {self.success_count} item(s) downloaded successfully", "completion", config=self.config)

        if self.config['general']['clear_temp'] and os.path.exists(temp_abs):
            for item in os.listdir(temp_abs):
                item_path = os.path.join(temp_abs, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception:
                    pass
            self.cli.show_info("Temp directory cleared")

        self._disconnect_warp()

    def _process_single(self, entry, idx, fmt, dest_abs, temp_abs, do_numbering, duplicate_action, total, archive_action='skip'):
        if not entry.get('id'):
            info = self.downloader.get_single_entry_fast(entry['url'])
            entry['id'] = info['id']
            entry['title'] = info['title']
            entry['playlist'] = None
        return self._process_single_entry(entry, idx, fmt, dest_abs, temp_abs,
                                          do_numbering, duplicate_action, total, archive_action)

    def _process_single_entry(self, entry, idx, fmt, dest_abs, temp_abs, do_numbering, duplicate_action, total, archive_action='skip'):
        self.cli.show_processing_item(entry['title'], idx, total)
        self.logger.info(f"Starting: {entry['title']}")

        safe = self._sanitize(entry['title'])[:40].rstrip(' ._-')
        job_dir = os.path.join(temp_abs, f"job_{idx:04d}_{safe}")
        os.makedirs(job_dir, exist_ok=True)

        video_info = {
            'title': entry['title'],
            'id': entry['id'],
            'url': entry['url'],
            'playlist': entry.get('playlist', 'N/A'),
            'destination': dest_abs,
        }

        os.makedirs(dest_abs, exist_ok=True)

        entry_fmt = entry.get('fmt', fmt)
        ext = '.' + self.config['video']['preferred_format'] if entry_fmt == 'video' else '.' + self.config['audio']['preferred_format']
        final_name = self._sanitize(entry['title'])
        if do_numbering:
            final_name = f"{idx:02d} - {final_name}"
        final_path = os.path.join(dest_abs, f"{final_name}{ext}")

        if duplicate_action == 'skip' and os.path.exists(final_path):
            self.skipped.record(entry, final_path, fmt)
            self.logger.info(
                f"Skipped (file exists): title={entry['title']}, url={entry['url']}, "
                f"id={entry['id']}, path={final_path}"
            )
            self.skip_count += 1
            shutil.rmtree(job_dir, ignore_errors=True)
            return 'skip'

        if archive_action != 'redownload' and entry.get('id') and self.archive.is_downloaded(entry['id']):
            if not os.path.exists(final_path):
                if archive_action == 'ask':
                    title_short = entry.get('title', entry['id'])[:60]
                    self.cli.console.print(f"[yellow]Video already in archive (file not found at destination):[/]")
                    self.cli.console.print(f"  [dim]- {title_short}[/]")
                    while True:
                        choice = self.cli.timed_input("[bold yellow]Redownload this video?[/] (y/N): ").lower()
                        if choice in ('y', 'yes'):
                            break
                        if choice in ('', 'n', 'no'):
                            self.skipped.record(entry, '(archive)', fmt)
                            self.logger.info(f"Skipped (archive): title={entry['title']}, id={entry['id']}")
                            self.skip_count += 1
                            shutil.rmtree(job_dir, ignore_errors=True)
                            return 'skip'
                else:
                    title_short = entry.get('title', entry['id'])[:60]
                    self.cli.show_info(f"[{idx}/{total}] Skipping (already in archive): {title_short}")
                    self.skipped.record(entry, '(archive)', fmt)
                    self.logger.info(f"Skipped (archive): title={entry['title']}, id={entry['id']}")
                    self.skip_count += 1
                    shutil.rmtree(job_dir, ignore_errors=True)
                    return 'skip'

        try:
            if entry_fmt == 'video':
                self.cli.show_info(f"[{idx}/{total}] Downloading video...")
                main_file = self.downloader.download_video(entry, job_dir, entry.get('chosen_format'))
                if not main_file:
                    raise RuntimeError("No media file produced")

                print(flush=True)
                self.cli.show_info(f"[{idx}/{total}] Downloading subtitles...")
                sub_files = {}
                try:
                    sub_files = self.downloader.download_subtitles(entry, job_dir)
                    if not sub_files:
                        self.sub_fail_count += 1
                        self.failed.record(video_info, "Subtitle download failed (no subtitle file produced)")
                        self.logger.error(f"Subtitle download failed for {entry['title']}: no file produced")
                except Exception as sub_err:
                    self.sub_fail_count += 1
                    cleaned = self._clean_error(sub_err)
                    self.failed.record(video_info, f"Subtitle download failed: {cleaned}")
                    self.logger.error(f"Subtitle download failed for {entry['title']}: {cleaned}")

                if sub_files:
                    self.cli.show_info(f"[{idx}/{total}] Converting subtitles to SRT...")
                    for lang, sub_path in list(sub_files.items()):
                        try:
                            sub_files[lang] = self.remuxer.convert_subtitle_to_srt(sub_path)
                        except Exception as conv_err:
                            self.sub_fail_count += 1
                            cleaned = self._clean_error(conv_err)
                            self.failed.record(video_info, f"Subtitle conversion failed ({lang}): {cleaned}")
                            self.logger.error(f"Subtitle conversion failed for {entry['title']} ({lang}): {cleaned}")
                            del sub_files[lang]

                if sub_files:
                    self.cli.show_info(f"[{idx}/{total}] Cleaning subtitles...")
                    for lang, sub_path in list(sub_files.items()):
                        try:
                            sub_files[lang] = self.subcleaner.clean_subtitle_file(sub_path)
                        except Exception as clean_err:
                            self.sub_fail_count += 1
                            cleaned = self._clean_error(clean_err)
                            self.failed.record(video_info, f"Subtitle cleaning failed ({lang}): {cleaned}")
                            self.logger.error(f"Subtitle cleaning failed for {entry['title']} ({lang}): {cleaned}")
                            del sub_files[lang]

                if sub_files:
                    self.cli.show_info(f"[{idx}/{total}] Splitting subtitle into karaoke lines...")
                    for lang, sub_path in list(sub_files.items()):
                        try:
                            sub_files[lang] = self.remuxer.split_subtitle_lines(sub_path)
                        except Exception as split_err:
                            self.logger.warn(f"Subtitle split failed ({lang}): {split_err}")

                transliterate = self.config['subtitle'].get('transliterate', '')
                if transliterate and sub_files:
                    self.cli.show_info(f"[{idx}/{total}] Transliterating to romaji...")
                    for lang, sub_path in list(sub_files.items()):
                        try:
                            sub_files[lang] = self.transliterator.transliterate_file(sub_path, lang)
                        except Exception as tr_err:
                            self.logger.warn(f"Transliteration failed ({lang}): {tr_err}")

                final_path = self._handle_duplicate_path(final_path, duplicate_action)

                if sub_files:
                    self.cli.show_info(f"[{idx}/{total}] Embedding subtitles...")
                    self.remuxer.embed_subtitles(main_file, sub_files, final_path)
                else:
                    self.cli.show_info(f"[{idx}/{total}] Finalizing video...")
                    self._copy_or_convert_video(main_file, final_path, job_dir)
            else:
                self.cli.show_info(f"[{idx}/{total}] Downloading audio...")
                main_file = self.downloader.download_audio(entry, job_dir, entry.get('chosen_format'))
                if not main_file:
                    raise RuntimeError("No media file produced")

                print(flush=True)
                self.cli.show_info(f"[{idx}/{total}] Downloading subtitles...")
                sub_files = {}
                try:
                    sub_files = self.downloader.download_subtitles(entry, job_dir)
                    if not sub_files:
                        self.sub_fail_count += 1
                        self.failed.record(video_info, "Subtitle download failed (no subtitle file produced)")
                        self.logger.error(f"Subtitle download failed for {entry['title']}: no file produced")
                except Exception as sub_err:
                    self.sub_fail_count += 1
                    cleaned = self._clean_error(sub_err)
                    self.failed.record(video_info, f"Subtitle download failed: {cleaned}")
                    self.logger.error(f"Subtitle download failed for {entry['title']}: {cleaned}")

                if sub_files:
                    self.cli.show_info(f"[{idx}/{total}] Converting subtitles to SRT...")
                    for lang, sub_path in list(sub_files.items()):
                        try:
                            sub_files[lang] = self.remuxer.convert_subtitle_to_srt(sub_path)
                        except Exception as conv_err:
                            self.sub_fail_count += 1
                            cleaned = self._clean_error(conv_err)
                            self.failed.record(video_info, f"Subtitle conversion failed ({lang}): {cleaned}")
                            self.logger.error(f"Subtitle conversion failed for {entry['title']} ({lang}): {cleaned}")
                            del sub_files[lang]

                if sub_files:
                    self.cli.show_info(f"[{idx}/{total}] Cleaning subtitles...")
                    for lang, sub_path in list(sub_files.items()):
                        try:
                            sub_files[lang] = self.subcleaner.clean_subtitle_file(sub_path)
                        except Exception as clean_err:
                            self.sub_fail_count += 1
                            cleaned = self._clean_error(clean_err)
                            self.failed.record(video_info, f"Subtitle cleaning failed ({lang}): {cleaned}")
                            self.logger.error(f"Subtitle cleaning failed for {entry['title']} ({lang}): {cleaned}")
                            del sub_files[lang]

                if sub_files:
                    self.cli.show_info(f"[{idx}/{total}] Splitting subtitle into karaoke lines...")
                    for lang, sub_path in list(sub_files.items()):
                        try:
                            sub_files[lang] = self.remuxer.split_subtitle_lines(sub_path)
                        except Exception as split_err:
                            self.logger.warn(f"Subtitle split failed ({lang}): {split_err}")

                transliterate = self.config['subtitle'].get('transliterate', '')
                if transliterate and sub_files:
                    self.cli.show_info(f"[{idx}/{total}] Transliterating to romaji...")
                    for lang, sub_path in list(sub_files.items()):
                        try:
                            sub_files[lang] = self.transliterator.transliterate_file(sub_path, lang)
                        except Exception as tr_err:
                            self.logger.warn(f"Transliteration failed ({lang}): {tr_err}")

                final_path = self._handle_duplicate_path(final_path, duplicate_action)

                if sub_files:
                    self.cli.show_info(f"[{idx}/{total}] Embedding subtitles into audio...")
                    self.remuxer.embed_subtitles_into_audio(main_file, sub_files, final_path)
                else:
                    self.cli.show_info(f"[{idx}/{total}] Finalizing audio...")
                    self._copy_or_convert_audio(main_file, final_path, job_dir)

            cs = self.config.get('chapter_splitter', {})
            if cs.get('enabled', False) and entry_fmt == 'video':
                self.cli.show_info(f"[{idx}/{total}] Checking for chapters...")
                try:
                    chapters = self.remuxer.get_chapters(final_path)
                    if chapters:
                        self.cli.show_info(f"[{idx}/{total}] Splitting {len(chapters)} chapters...")
                        ext = self.config['video']['preferred_format']
                        splits = self.remuxer.split_by_chapters(final_path, os.path.dirname(final_path), entry['title'], ext)
                        self.cli.show_success(f"Split into {len(splits)} chapter files")
                    else:
                        self.cli.show_info(f"[{idx}/{total}] No chapters found")
                except Exception as ch_err:
                    self.cli.show_warning(f"Chapter split failed: {self._clean_error(ch_err)}")

            self.archive.mark_downloaded(entry['id'])
            self.stats.record_download(entry['title'], entry_fmt, os.path.getsize(final_path))
            self.cli.show_success(entry['title'])
            self.logger.info(f"Completed: {entry['title']} -> {final_path}")
            shutil.rmtree(job_dir, ignore_errors=True)
            return 'success'

        except Exception as e:
            error_msg = self._clean_error(str(e))
            self.cli.show_error(f"{entry['title']}: {error_msg}")
            self.logger.error(f"Failed: {entry['title']} - {error_msg}")
            self.failed.record(video_info, error_msg)
            if self._sounds_enabled:
                _notify("Download Failed", f"{entry['title'][:50]}: {error_msg[:80]}", "download_error", config=self.config)
            shutil.rmtree(job_dir, ignore_errors=True)
            return False

    def _handle_duplicate_path(self, path, action):
        if action == 'overwrite' or not os.path.exists(path):
            return path
        if action == 'skip':
            return path
        base, ext = os.path.splitext(path)
        counter = 1
        while os.path.exists(f"{base}_{counter}{ext}"):
            counter += 1
        return f"{base}_{counter}{ext}"

    def _copy_or_convert_video(self, src, dst, work_dir):
        if src.lower().endswith('.mp4'):
            shutil.copy2(src, dst)
        else:
            converted = os.path.join(work_dir, '_converted.mp4')
            self.remuxer.convert_video(src, converted)
            shutil.copy2(converted, dst)

    def _copy_or_convert_audio(self, src, dst, work_dir):
        audio_exts = {'.m4a', '.mp3', '.opus', '.aac', '.flac', '.wav', '.ogg'}
        if os.path.splitext(src)[1].lower() in audio_exts:
            shutil.copy2(src, dst)
        else:
            converted = os.path.join(work_dir, '_converted.m4a')
            self.remuxer.convert_audio(src, converted)
            shutil.copy2(converted, dst)
