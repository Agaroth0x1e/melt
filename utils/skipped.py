import os
from datetime import datetime

class SkippedTracker:
    def __init__(self, skipped_path):
        self.skipped_path = skipped_path
        os.makedirs(os.path.dirname(skipped_path), exist_ok=True)

    def record(self, entry, final_path, fmt):
        size = 0
        try:
            if os.path.exists(final_path):
                size = os.path.getsize(final_path)
        except OSError:
            pass
        size_str = f"{size / 1024:.1f} KB" if size < 1048576 else f"{size / 1048576:.1f} MB"
        with open(self.skipped_path, 'a', encoding='utf-8') as f:
            f.write(f"{'='*60}\n")
            f.write(f"Time       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Title      : {entry.get('title', 'Unknown')}\n")
            f.write(f"ID         : {entry.get('id', 'Unknown')}\n")
            f.write(f"URL        : {entry.get('url', 'Unknown')}\n")
            f.write(f"Playlist   : {entry.get('playlist', 'N/A')}\n")
            f.write(f"Format     : {fmt}\n")
            f.write(f"File       : {final_path}\n")
            f.write(f"File Size  : {size_str}\n")
            f.write(f"{'='*60}\n\n")
