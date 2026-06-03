import os
from datetime import datetime

class FailedTracker:
    def __init__(self, failed_path):
        self.failed_path = failed_path
        os.makedirs(os.path.dirname(failed_path), exist_ok=True)

    def record(self, video_info, error):
        with open(self.failed_path, 'a', encoding='utf-8') as f:
            f.write(f"{'='*60}\n")
            f.write(f"Time      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Title     : {video_info.get('title', 'Unknown')}\n")
            f.write(f"ID        : {video_info.get('id', 'Unknown')}\n")
            f.write(f"URL       : {video_info.get('url', 'Unknown')}\n")
            f.write(f"Playlist  : {video_info.get('playlist', 'N/A')}\n")
            f.write(f"Dest      : {video_info.get('destination', 'Unknown')}\n")
            f.write(f"Error     : {error}\n")
            f.write(f"{'='*60}\n\n")
