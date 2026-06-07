import os

class Archive:
    def __init__(self, archive_path):
        self.archive_path = archive_path
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)

    def is_downloaded(self, video_id):
        if not os.path.exists(self.archive_path):
            return False
        with open(self.archive_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() == video_id:
                    return True
        return False

    def mark_downloaded(self, video_id):
        if self.is_downloaded(video_id):
            return
        with open(self.archive_path, 'a', encoding='utf-8') as f:
            f.write(video_id + '\n')
