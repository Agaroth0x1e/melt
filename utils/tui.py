import os
import sys
from datetime import datetime

from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich import box

from utils.stats import StatsTracker


def _format_bytes(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _build_dashboard(stats_data, config):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="stats", ratio=1),
        Layout(name="recent", ratio=2),
    )

    header_text = Text("MelT Dashboard", style="bold cyan")
    from main import VERSION
    header_text.append(f"  v{VERSION}", style="dim")
    header_text.append(f"  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="green")
    layout["header"].update(Panel(header_text, box=box.ROUNDED))

    stats = stats_data.get('stats', stats_data)
    t = Table.grid(padding=(0, 2))
    t.add_row("[bold]Total downloads[/]", str(stats.get('total_downloads', 0)))
    t.add_row("[bold]Total size[/]", _format_bytes(stats.get('total_bytes', 0)))
    last = stats.get('last_download', '')
    if last:
        try:
            dt = datetime.fromisoformat(last)
            last = dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            pass
    t.add_row("[bold]Last download[/]", last)
    t.add_row("[bold]Config[/]", config.config_path)
    layout["stats"].update(Panel(t, title="Statistics", box=box.ROUNDED))

    history = stats.get('history', [])
    table = Table(box=box.SIMPLE)
    table.add_column("Title", ratio=3)
    table.add_column("Format", ratio=1)
    table.add_column("Size", ratio=1)
    table.add_column("Time", ratio=2)
    for entry in history[:15]:
        ts = entry.get('time', '')
        try:
            dt = datetime.fromisoformat(ts)
            ts = dt.strftime('%H:%M %m-%d')
        except Exception:
            pass
        table.add_row(
            entry.get('title', '?')[:50],
            entry.get('fmt', '?'),
            _format_bytes(entry.get('size', 0)),
            ts,
        )
    if not history:
        table.add_row("[dim]No downloads yet[/]", "", "", "")
    layout["recent"].update(Panel(table, title="Recent Downloads", box=box.ROUNDED))

    footer = Text(" [q] Quit  |  [r] Refresh  |  [d] Open downloads folder", style="dim")
    layout["footer"].update(Panel(footer, box=box.ROUNDED))
    return layout


def run_dashboard(config, logger):
    from rich.console import Console
    console = Console()
    stats = StatsTracker(config)
    try:
        with Live(console=console, screen=True, auto_refresh=False) as live:
            live.update(_build_dashboard(stats.get(), config))
            while True:
                try:
                    if sys.platform == 'win32':
                        import msvcrt
                        import time as _t
                        if msvcrt.kbhit():
                            key = msvcrt.getch().decode('utf-8', errors='replace').lower()
                            if key == 'q':
                                break
                            elif key == 'r':
                                live.update(_build_dashboard(stats.get(), config))
                                live.refresh()
                            elif key == 'd':
                                d = config.resolve_path(config['general']['downloads_dir'])
                                if os.path.exists(d):
                                    os.startfile(d)
                        else:
                            _t.sleep(0.5)
                    else:
                        import select
                        if select.select([sys.stdin], [], [], 1)[0]:
                            key = sys.stdin.read(1)
                            if key == 'q':
                                break
                            elif key == 'r':
                                live.update(_build_dashboard(stats.get(), config))
                                live.refresh()
                            elif key == 'd':
                                d = config.resolve_path(config['general']['downloads_dir'])
                                if os.path.exists(d):
                                    os.startfile(d)
                    live.update(_build_dashboard(stats.get(), config))
                except Exception:
                    break
    except KeyboardInterrupt:
        pass
