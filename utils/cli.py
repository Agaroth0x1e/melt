import sys
import time as time_module

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, IntPrompt
from rich.align import Align
from rich import box

console = Console()


def timed_prompt(prompt_text, timeout, default):
    console.print(prompt_text, end="")
    sys.stderr.flush()
    sys.stdout.flush()

    if timeout < 0:
        line = input()
        return line.strip() if line.strip() else default

    _any_key = False
    start = time_module.time()
    while time_module.time() - start < timeout:
        if sys.platform == 'win32':
            import msvcrt
            if msvcrt.kbhit():
                _any_key = True
                break
        else:
            import select
            if select.select([sys.stdin], [], [], 0)[0]:
                _any_key = True
                break
        time_module.sleep(0.05)

    if not _any_key:
        print()
        return default

    line = input()
    return line.strip() if line.strip() else default


class CLI:
    def __init__(self, config):
        self.config = config
        self.console = console

    def show_banner(self):
        banner = Text("""
    +====================+
    |       MelT         |
    |      v1.1.0        |
    +====================+
""", style="bold cyan")
        self.console.print(Align.center(banner))
        self.console.print()

    def ask_url(self):
        return console.input("[bold yellow]Enter YouTube URL or URLs[/]: ").strip()

    def ask_reuse_settings(self, prev):
        self.console.print("\n[bold]Previous session settings:[/]")
        fmt_label = {'video': 'Video', 'audio': 'Audio', 'both': 'Both (Video + Audio)'}.get(prev.get('fmt'), 'Video')
        self.console.print(f"  [cyan]Format:[/]        {fmt_label}")
        self.console.print(f"  [cyan]Destination:[/]   {prev.get('dest', '?')}")
        self.console.print(f"  [cyan]Numbering:[/]     {'Yes' if prev.get('numbering') else 'No'}")
        self.console.print(f"  [cyan]On Duplicate:[/]  {prev.get('duplicate_action', 'skip')}")
        self.console.print(f"  [cyan]Dry Run:[/]       {'Yes' if prev.get('dry_run') else 'No'}")
        timeout = self.config['general']['timeout_seconds']
        default_reuse = self.config['general'].get('default_reuse', True)
        default_ans = 'yes' if default_reuse else 'no'
        result = timed_prompt(
            f"[bold yellow]Reuse these settings?[/] (Y=yes / n=no / m=modify / s=show again / q=quit) [bold](default: {'yes' if default_reuse else 'no'})[/]: ",
            timeout, default_ans
        ).strip().lower()
        if result in ('q', 'quit', 'exit'):
            return 'exit'
        if result in ('n', 'no'):
            return 'no'
        if result in ('s', 'show'):
            return self.ask_reuse_settings(prev)
        if result in ('m', 'modify'):
            return 'modify'
        return 'yes'

    def ask_format(self):
        timeout = self.config['general']['timeout_seconds']
        default = self.config['general']['default_format']
        mapping = {'1': 'video', '2': 'audio', '3': 'both'}
        def_key = {'video': '1', 'audio': '2', 'both': '3'}.get(default, '1')
        result = timed_prompt(
            f"[bold yellow]Download format[/] (1: video, 2: audio, 3: both) [bold](default: {default})[/]: ",
            timeout, def_key
        )
        return mapping.get(result.strip(), default)

    def ask_playlist_range(self, total, identifier=None):
        timeout = self.config['general']['timeout_seconds']
        label = f" for \"{identifier}\"" if identifier else ""
        result = timed_prompt(
            f"[bold yellow]Playlist range{label}[/] (e.g. 1-5, 1,3,5 or 'all') [bold](default: all)[/]: ",
            timeout, 'all'
        )
        return result if result else 'all'

    def ask_duplicate_action(self):
        timeout = self.config['general']['timeout_seconds']
        result = timed_prompt(
            "[bold yellow]On duplicate[/] (keep/overwrite/skip) [bold](default: skip)[/]: ",
            timeout, 'skip'
        )
        if result.lower().strip() in ('keep', 'overwrite', 'skip'):
            return result.lower().strip()
        return 'skip'

    def ask_archive_action(self):
        timeout = self.config['general']['timeout_seconds']
        result = timed_prompt(
            "[bold yellow]Archive action[/] (skip/ask/redownload) [bold](default: skip)[/]: ",
            timeout, 'skip'
        )
        val = result.lower().strip()
        if val in ('skip', 'ask', 'redownload'):
            return val
        return 'skip'

    def ask_destination(self):
        timeout = self.config['general']['timeout_seconds']
        default = self.config['general']['downloads_dir']
        result = timed_prompt(
            f"[bold yellow]Destination folder[/] [bold](default: {default})[/]: ",
            timeout, default
        )
        return result if result else default

    def show_options_summary(self, options):
        table = Table(box=box.ROUNDED, title="[bold]Current Configuration[/]", title_justify="center")
        table.add_column("Option", style="cyan", width=20)
        table.add_column("Value", style="green")

        for key, value in options.items():
            table.add_row(key, str(value))

        self.console.print(table)
        self.console.print()

    def show_format_preview(self, title, formats):
        self.console.print(f"\n[bold]Available formats for:[/] {title[:60]}")
        table = Table(box=box.SIMPLE)
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Ext", width=5)
        table.add_column("Type", width=6)
        table.add_column("Quality", width=10)
        table.add_column("Codec", width=8)
        table.add_column("Size", width=10)
        for fmt_id, ext, typ, quality, codec, size in formats:
            size_str = f"{size / 1048576:.1f} MB" if size else "~"
            table.add_row(fmt_id, ext, typ, quality, codec, size_str)
        self.console.print(table)
        choice = console.input("[bold yellow]Enter format ID to use[/] (or press Enter for auto): ")
        return choice.strip() if choice.strip() else None

    def show_start_prompt(self, timeout, force_modify=False):
        if force_modify:
            self.console.print("[cyan]Modify mode — change any option before starting[/]")
            return 'm'
        result = timed_prompt(
            f"[bold yellow]Press Enter to start[/] (auto-starts in {timeout}s) [bold]or type 'm' to modify options, Ctrl+C to abort[/]: ",
            timeout, 'start'
        )
        return result

    def ask_modify_option(self, options):
        self.console.print("[bold cyan]Select option to modify:[/]")
        keys = list(options.keys())
        for i, key in enumerate(keys, 1):
            self.console.print(f"  [{i}] {key}")
        self.console.print(f"  [{len(keys)+1}] Start download")

        choice = IntPrompt.ask("[bold yellow]Your choice[/]", default=len(keys)+1)
        if 1 <= choice <= len(keys):
            return keys[choice-1]
        return None

    def show_processing_item(self, item_name, current, total):
        self.console.print(f"[cyan][{current}/{total}][/] Processing: [bold]{item_name}[/]")

    def show_success(self, message):
        self.console.print(f"[green]OK[/] {message}")

    def show_error(self, message):
        self.console.print(f"[red]FAIL[/] {message}")

    def show_warning(self, message):
        self.console.print(f"[yellow]WARN[/] {message}")

    def show_info(self, message):
        self.console.print(f"[blue]INFO[/] {message}")

    def show_completion(self, success_count, fail_count, dest, log_path, failed_path, sub_fail_count=0, elapsed=0, skip_count=0, skipped_path=None):
        self.console.print()
        elapsed_str = ""
        if elapsed:
            mins, secs = divmod(int(elapsed), 60)
            hrs, mins = divmod(mins, 60)
            if hrs:
                elapsed_str = f"[bold]Time elapsed:[/] {hrs}h {mins}m {secs}s"
            elif mins:
                elapsed_str = f"[bold]Time elapsed:[/] {mins}m {secs}s"
            else:
                elapsed_str = f"[bold]Time elapsed:[/] {secs}s"
        body = (
            f"[green]Successfully processed: {success_count}[/]\n"
            f"[red]Failed: {fail_count}[/]"
        )
        if skip_count > 0:
            body += f"\n[yellow]Skipped (already exists): {skip_count}[/]"
        if sub_fail_count > 0:
            body += f"\n[yellow]Subtitle failures: {sub_fail_count} (videos still downloaded)[/]"
        body += f"\n[bold]Delivered to:[/] {dest}"
        if elapsed_str:
            body += f"\n{elapsed_str}"
        show_extra = False
        extra_parts = []
        if fail_count > 0 or sub_fail_count > 0:
            show_extra = True
            extra_parts.append(f"Check [bold]{log_path}[/] for details")
            extra_parts.append(f"Check [bold]{failed_path}[/] for failure records")
        if skip_count > 0 and skipped_path:
            show_extra = True
            extra_parts.append(f"Check [bold]{skipped_path}[/] for skipped/duplicate records")
        if show_extra:
            body += f"\n\n[yellow]Some operations had issues.[/]\n" + "\n".join(extra_parts)
        panel = Panel(
            body,
            title="[bold]Done[/]",
            box=box.DOUBLE_EDGE
        )
        self.console.print(panel)

    def show_main_menu(self, show_table=True):
        if show_table:
            self.console.print()
            table = Table(box=box.ROUNDED, title="[bold cyan]MelT Main Menu[/]", title_justify="center", border_style="cyan")
            table.add_column("Option", style="yellow", width=6)
            table.add_column("Action", style="green", width=24)
            table.add_column("Description", style="white", width=40)
            table.add_row("1", "Download from URL", "Enter URLs, playlists, batch files")
            table.add_row("2", "Search YouTube", "Search and download results")
            table.add_row("3", "View Analytics", "Download statistics and trends")
            table.add_row("4", "Open Dashboard", "TUI live dashboard")
            table.add_row("5", "Scheduled Downloads", "Manage recurring downloads")
            table.add_row("6", "Auto-Rules", "Manage download rules")
            table.add_row("7", "Watch Folder", "Start folder watcher")
            table.add_row("8", "Cloud Sync", "Sync config via git")
            table.add_row("9", "Show Help", "Inline help")
            table.add_row("q", "Exit", "Quit MelT")
            self.console.print(table)
            self.console.print()
        return console.input("[bold yellow]Choose an option[/]: ").strip().lower()

    def show_schedule_menu(self):
        self.console.print("[bold cyan]Scheduled Downloads[/]")
        t = Table(box=box.SIMPLE)
        t.add_column("Option", style="yellow", width=6)
        t.add_column("Action", style="green")
        t.add_row("1", "List all jobs")
        t.add_row("2", "Add a job")
        t.add_row("3", "Remove a job")
        t.add_row("4", "Start scheduler daemon")
        t.add_row("b", "Back to main menu")
        self.console.print(t)
        return console.input("[bold yellow]Schedule option[/] (default: b): ").strip().lower() or 'b'

    def show_rules_menu(self):
        self.console.print("[bold cyan]Auto-Rules[/]")
        t = Table(box=box.SIMPLE)
        t.add_column("Option", style="yellow", width=6)
        t.add_column("Action", style="green")
        t.add_row("1", "List all rules")
        t.add_row("2", "Add a rule")
        t.add_row("3", "Remove a rule")
        t.add_row("b", "Back to main menu")
        self.console.print(t)
        return console.input("[bold yellow]Rules option[/] (default: b): ").strip().lower() or 'b'

    def show_sync_menu(self):
        self.console.print("[bold cyan]Cloud Sync[/]")
        t = Table(box=box.SIMPLE)
        t.add_column("Option", style="yellow", width=6)
        t.add_column("Action", style="green")
        t.add_row("1", "Initialize sync repo")
        t.add_row("2", "Push changes")
        t.add_row("3", "Pull changes")
        t.add_row("4", "Show status")
        t.add_row("b", "Back to main menu")
        self.console.print(t)
        return console.input("[bold yellow]Sync option[/] (default: b): ").strip().lower() or 'b'

    def ask_continue(self):
        return console.input(
            "[bold yellow]Enter URLs to download more, or type 'exit' to quit, or 'menu' for main menu[/]: "
        ).strip()
