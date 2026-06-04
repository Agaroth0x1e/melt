import os
import json
from datetime import datetime
from collections import Counter, defaultdict


def _fmt_bytes(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def show_analytics(stats_path):
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.config import _working_dir

    if not os.path.exists(stats_path):
        print("No analytics data yet. Download something first!")
        return

    try:
        with open(stats_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to load analytics: {e}")
        return

    history = data.get('history', [])
    if not history:
        print("No download history yet.")
        return

    total = data.get('total_downloads', 0)
    total_bytes = data.get('total_bytes', 0)
    last = data.get('last_download', '')

    fmt_counts = Counter(h.get('fmt', '?') for h in history)
    monthly = Counter()
    for h in history:
        try:
            dt = datetime.fromisoformat(h.get('time', ''))
            monthly[dt.strftime('%Y-%m')] += 1
        except Exception:
            pass

    try:
        from rich.table import Table
        from rich.console import Console
        from rich.panel import Panel
        from rich import box
        from rich.text import Text
        console = Console()

        console.print()
        console.rule("[bold cyan]MelT Analytics")
        console.print()

        g = Table.grid(padding=(0, 2))
        g.add_row("[bold]Total downloads[/]", str(total))
        g.add_row("[bold]Total size[/]", _fmt_bytes(total_bytes))
        g.add_row("[bold]Average size[/]", _fmt_bytes(total_bytes / total) if total else '0 B')
        if last:
            try:
                dt = datetime.fromisoformat(last)
                g.add_row("[bold]Last download[/]", dt.strftime('%Y-%m-%d %H:%M'))
            except Exception:
                g.add_row("[bold]Last download[/]", last)
        try:
            first = datetime.fromisoformat(history[-1].get('time', ''))
            g.add_row("[bold]First download[/]", first.strftime('%Y-%m-%d %H:%M'))
        except Exception:
            pass
        console.print(Panel(g, title="Overview", box=box.ROUNDED))

        ft = Table(box=box.SIMPLE)
        ft.add_column("Format", style="bold")
        ft.add_column("Count", justify="right")
        ft.add_column("Size", justify="right")
        total_counts = sum(fmt_counts.values())
        for fmt_name in sorted(fmt_counts):
            n = fmt_counts[fmt_name]
            fmt_size = sum(h.get('size', 0) for h in history if h.get('fmt') == fmt_name)
            pct = n / total_counts * 100
            bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
            ft.add_row(fmt_name, str(n), _fmt_bytes(fmt_size))
        console.print(Panel(ft, title="By Format", box=box.ROUNDED))
        console.print()

        mt = Table(box=box.SIMPLE)
        mt.add_column("Month", style="bold")
        mt.add_column("Downloads", justify="right")
        mt.add_column("")
        max_count = max(monthly.values()) if monthly else 1
        for month in sorted(monthly):
            n = monthly[month]
            bar_len = int(n / max_count * 20)
            bar = '█' * bar_len + '░' * (20 - bar_len)
            mt.add_row(month, str(n), bar)
        console.print(Panel(mt, title="By Month", box=box.ROUNDED))
        console.print()

        rt = Table(box=box.SIMPLE)
        rt.add_column("Title", ratio=3)
        rt.add_column("Format", ratio=1)
        rt.add_column("Size", ratio=1)
        rt.add_column("Date", ratio=2)
        for h in history[:10]:
            ts = h.get('time', '')
            try:
                dt = datetime.fromisoformat(ts)
                ts = dt.strftime('%Y-%m-%d %H:%M')
            except Exception:
                pass
            rt.add_row(h.get('title', '?')[:50], h.get('fmt', '?'), _fmt_bytes(h.get('size', 0)), ts)
        console.print(Panel(rt, title="Last 10 Downloads", box=box.ROUNDED))
        console.print()

    except ImportError:
        print(f"\n{'='*50}")
        print(f"MelT Analytics")
        print(f"{'='*50}")
        print(f"Total downloads: {total}")
        print(f"Total size: {_fmt_bytes(total_bytes)}")
        print(f"Last download: {last}")
        print(f"\nBy format:")
        for fmt_name, n in fmt_counts.most_common():
            print(f"  {fmt_name}: {n}")
        print(f"\nBy month:")
        for month in sorted(monthly):
            print(f"  {month}: {monthly[month]}")


class StatsTracker:
    def __init__(self, config):
        self.config = config
        self._path = config.resolve_path(os.path.join('logs', 'stats.json'))
        self._data = self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {'total_downloads': 0, 'total_bytes': 0, 'history': []}

    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=2)

    def record_download(self, title, fmt, size=0):
        self._data['total_downloads'] += 1
        self._data['total_bytes'] += size
        self._data['last_download'] = datetime.now().isoformat()
        entry = {
            'title': title,
            'fmt': fmt,
            'size': size,
            'time': datetime.now().isoformat(),
        }
        self._data['history'].insert(0, entry)
        self._data['history'] = self._data['history'][:50]
        self._save()

    def get(self):
        return self._data
