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
        signal.signal(signal.SIGINT, self._handle_sigint)
        atexit.register(self._cleanup_temp)

    QUEUE_FILE = '_resume_queue.json'

    HELP_URL_TEXT = """
  [bold cyan]Inline Help[/]

  [bold]Basic usage:[/]
    Paste one or more YouTube URLs (space-separated).
    Use [bold]@file.txt[/] to load URLs from a text file.

  [bold]During prompts:[/]
    [green]Enter[/]              Accept default / auto-confirm
    [green]m[/]                  Modify options before starting
    [green]q[/] / [green]exit[/] / [green]quit[/]  Exit at most prompts

  [bold]Session-persistent options:[/]
    After first download, MelT remembers your settings
    and offers to reuse them for the next batch.

  [bold]Config:[/]
    Edit [bold]config/config.json[/] for permanent defaults
    (format, threads, timeout, numbering, etc.)
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

    def run(self, resume=False):
        if not resume:
            self.cli.show_banner()

        threads = self.config['general']['max_threads']
        do_numbering = self.config['general'].get('numbering', False)
        duplicate_action = self.config['general'].get('duplicate_action', 'skip')
        dry_run = self.config['general'].get('dry_run', False)

        if resume:
            queue = self._load_queue()
            if not queue:
                self.cli.show_error("No resume queue found")
                return
            fmt = queue['fmt']
            threads = queue.get('threads', threads)
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

        raw = ''
        while True:
            while True:
                if not raw:
                    raw = self.cli.ask_url()
                raw = raw.strip()
                if raw.lower() in ('exit', 'quit', 'q'):
                    return
                if raw.lower() == 'help':
                    self.cli.console.print(self.HELP_URL_TEXT)
                    raw = ''
                    continue
                urls = self._resolve_batch_urls(raw)
                raw = ''
                if not urls:
                    continue

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
                    else:
                        fmt = self.cli.ask_format()
                        dest = self.cli.ask_destination()
                else:
                    reuse = None
                    fmt = self.cli.ask_format()
                    dest = self.cli.ask_destination()

                if dest == self.config['general']['downloads_dir'] and fmt != 'both':
                    dest = os.path.join(dest, 'videos' if fmt == 'video' else 'audio')

                url_infos = []
                for url in urls:
                    short = url[:60]
                    self.cli.show_info(f"Analyzing {short}...")
                    try:
                        url_infos.append((url, self.downloader.inspect_url(url)))
                    except Exception as e:
                        self.cli.show_error(f"Skipping {url}: {e}")
                        self.logger.error(f"Failed to inspect {url}: {e}")

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
                        v = os.path.join(base_dest, 'videos') if base_dest == self.config['general']['downloads_dir'] else base_dest
                        a = os.path.join(base_dest, 'audio') if base_dest == self.config['general']['downloads_dir'] else base_dest
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

                        if self.config['general'].get('reverse_playlist', False):
                            entries = list(reversed(entries))

                        snapshot = self._load_playlist_snapshot(pl_id)
                        if snapshot:
                            self._show_playlist_diff(snapshot.get('videos', []), entries, pl_title)
                        self._save_playlist_snapshot(pl_id, pl_title, entries)

                        prange = self.cli.ask_playlist_range(len(entries), identifier=pl_title)
                        if prange.lower() != 'all':
                            entries = self._parse_range(prange, entries)

                        tmpl = self.config['general'].get('playlist_folder_template', '%(playlist_title)s')
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

                options = self._build_options(all_entries, fmt, dest, do_numbering, duplicate_action, dry_run)
                self.cli.show_options_summary(options)

                timeout = self.config['general']['timeout_seconds']
                mod_key = None
                _force_modify = (reuse == 'modify') if self._prev_settings else False
                while True:
                    action = self.cli.show_start_prompt(timeout, force_modify=_force_modify)
                    _force_modify = False
                    if action in ('start', ''):
                        break
                    if action.lower() == 'm':
                        mod_key = self.cli.ask_modify_option(options)
                        if mod_key is None:
                            break
                        if mod_key == 'Items':
                            self.cli.show_info("Enter new URL(s):")
                            break
                        new_val = self._modify_option(mod_key, fmt, dest, do_numbering, duplicate_action, dry_run)
                        if new_val is not None:
                            if mod_key == 'Format':
                                fmt = new_val
                            elif mod_key == 'Destination':
                                dest = new_val
                            elif mod_key == 'Numbering':
                                do_numbering = new_val
                            elif mod_key == 'On Duplicate':
                                duplicate_action = new_val
                            elif mod_key == 'Dry Run':
                                dry_run = new_val
                        continue
                    self.cli.show_warning("Invalid option. Press Enter to start or type 'm' to modify.")
                if action in ('start', ''):
                    break
                if mod_key == 'URLs':
                    continue
                break

            if self.config['general'].get('format_preview', False) and not any(e.get('chosen_format') for e in all_entries):
                unique_urls = list(dict.fromkeys(e['url'] for e in all_entries))
                for u in unique_urls[:1]:
                    try:
                        fmts = self.downloader.fetch_formats(u)
                        if fmts:
                            chosen = self.cli.show_format_preview(all_entries[0].get('title', u), fmts)
                            if chosen:
                                for e in all_entries:
                                    e['chosen_format'] = chosen
                    except Exception:
                        self.cli.show_warning("Could not fetch format preview")

            self._execute_all(all_entries, fmt, threads, do_numbering, duplicate_action, dry_run)

            self._save_prev_settings(fmt, dest, do_numbering, duplicate_action, dry_run)

            if self.config['general'].get('exit_on_complete', False):
                break

            answer = self.cli.ask_continue()
            if answer.lower() in ('exit', 'quit', 'q'):
                break
            raw = answer

    def batch_download(self, url, fmt, dest):
        threads = self.config['general']['max_threads']
        do_numbering = self.config['general'].get('numbering', False)
        duplicate_action = self.config['general'].get('duplicate_action', 'skip')
        dry_run = self.config['general'].get('dry_run', False)

        if dest == self.config['general']['downloads_dir'] and fmt != 'both':
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
                v = os.path.join(base_dest, 'videos') if base_dest == self.config['general']['downloads_dir'] else base_dest
                a = os.path.join(base_dest, 'audio') if base_dest == self.config['general']['downloads_dir'] else base_dest
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
                if self.config['general'].get('reverse_playlist', False):
                    entries = list(reversed(entries))
                tmpl = self.config['general'].get('playlist_folder_template', '%(playlist_title)s')
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

    def _save_prev_settings(self, fmt, dest, numbering, dup_action, dry_run):
        self._prev_settings = {
            'fmt': fmt,
            'dest': dest,
            'numbering': numbering,
            'duplicate_action': dup_action,
            'dry_run': dry_run,
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

    def _build_options(self, all_entries, fmt, dest, numbering, dup_action, dry_run=False):
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
            'Dry Run': 'Yes' if dry_run else 'No',
        }

    def _modify_option(self, key, fmt, dest, numbering, dup_action, dry_run=False):
        if key == 'Format':
            return self.cli.ask_format()
        elif key == 'Destination':
            return self.cli.ask_destination()
        elif key == 'Numbering':
            return not numbering
        elif key == 'On Duplicate':
            return self.cli.ask_duplicate_action()
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

    def _execute_all(self, all_entries, fmt, threads, do_numbering, duplicate_action, dry_run=False, resume=False):
        self.success_count = 0
        self.fail_count = 0
        self.sub_fail_count = 0
        self.skip_count = 0
        self._interrupted = False

        items = [(entry, idx + 1) for idx, entry in enumerate(all_entries)]
        if not items:
            return

        start_time = time.time()
        total = len(items)
        temp_abs = self.config.resolve_path(self.config['general']['temp_dir'])
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
                    do_numbering, duplicate_action, total
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

        log_file = self.config.resolve_path(self.config['general']['log_file'])
        failed_file = self.config.resolve_path(self.config['general']['failed_file'])
        skipped_file = self.config.resolve_path(self.config['general']['skipped_file'])
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

    def _process_single(self, entry, idx, fmt, dest_abs, temp_abs, do_numbering, duplicate_action, total):
        if not entry.get('id'):
            info = self.downloader.get_single_entry_fast(entry['url'])
            entry['id'] = info['id']
            entry['title'] = info['title']
            entry['playlist'] = None
        return self._process_single_entry(entry, idx, fmt, dest_abs, temp_abs,
                                          do_numbering, duplicate_action, total)

    def _process_single_entry(self, entry, idx, fmt, dest_abs, temp_abs, do_numbering, duplicate_action, total):
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

        try:
            if entry_fmt == 'video':
                self.cli.show_info(f"[{idx}/{total}] Downloading video...")
                main_file = self.downloader.download_video(entry, job_dir, entry.get('chosen_format'))
                if not main_file:
                    raise RuntimeError("No media file produced")

                self.cli.show_info(f"[{idx}/{total}] Downloading subtitles...")
                sub_file = None
                clean_sub = None
                try:
                    sub_file = self.downloader.download_subtitles(entry, job_dir)
                    if sub_file is None:
                        self.sub_fail_count += 1
                        self.failed.record(video_info, "Subtitle download failed (no subtitle file produced)")
                        self.logger.error(f"Subtitle download failed for {entry['title']}: no file produced")
                except Exception as sub_err:
                    self.sub_fail_count += 1
                    cleaned = self._clean_error(sub_err)
                    self.failed.record(video_info, f"Subtitle download failed: {cleaned}")
                    self.logger.error(f"Subtitle download failed for {entry['title']}: {cleaned}")

                if sub_file:
                    self.cli.show_info(f"[{idx}/{total}] Converting subtitles to SRT...")
                    try:
                        sub_file = self.remuxer.convert_subtitle_to_srt(sub_file)
                    except Exception as conv_err:
                        self.sub_fail_count += 1
                        cleaned = self._clean_error(conv_err)
                        self.failed.record(video_info, f"Subtitle conversion failed: {cleaned}")
                        self.logger.error(f"Subtitle conversion failed for {entry['title']}: {cleaned}")
                        sub_file = None

                if sub_file:
                    self.cli.show_info(f"[{idx}/{total}] Cleaning subtitles...")
                    try:
                        clean_sub = self.subcleaner.clean_subtitle_file(sub_file)
                    except Exception as clean_err:
                        self.sub_fail_count += 1
                        cleaned = self._clean_error(clean_err)
                        self.failed.record(video_info, f"Subtitle cleaning failed: {cleaned}")
                        self.logger.error(f"Subtitle cleaning failed for {entry['title']}: {cleaned}")

                final_path = self._handle_duplicate_path(final_path, duplicate_action)

                if clean_sub and os.path.exists(clean_sub):
                    self.cli.show_info(f"[{idx}/{total}] Embedding subtitles...")
                    self.remuxer.embed_subtitles(main_file, clean_sub, final_path)
                else:
                    self.cli.show_info(f"[{idx}/{total}] Finalizing video...")
                    self._copy_or_convert_video(main_file, final_path, job_dir)
            else:
                self.cli.show_info(f"[{idx}/{total}] Downloading audio...")
                main_file = self.downloader.download_audio(entry, job_dir, entry.get('chosen_format'))
                if not main_file:
                    raise RuntimeError("No media file produced")

                final_path = self._handle_duplicate_path(final_path, duplicate_action)

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
