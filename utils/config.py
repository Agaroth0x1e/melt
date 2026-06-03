import json
import os
import sys
import shutil


def _is_bundled():
    return getattr(sys, 'frozen', False)


def _bundle_dir():
    if _is_bundled():
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _working_dir():
    if _is_bundled():
        return os.path.abspath(os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(_working_dir(), 'config', 'config.json')

        self.working_dir = _working_dir()
        self.bundle_dir = _bundle_dir()
        self.config_path = config_path
        self.config = self.load()

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        bundled = os.path.join(self.bundle_dir, 'config', 'config.json')
        if os.path.exists(bundled):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            shutil.copy2(bundled, self.config_path)
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        cfg = self.defaults()
        self.config = cfg
        self.save()
        return cfg

    def save(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)

    def defaults(self):
        return {
            "general": {
                "temp_dir": "temp",
                "downloads_dir": "downloads",
                "archive_file": "archive/archive.txt",
                "log_file": "log/log.txt",
                "failed_file": "failed/failed.txt",
                "clear_temp": True,
                "default_format": "video",
                "max_threads": 10,
                "timeout_seconds": 5,
                "filename_template": "%(title)s.%(ext)s",
                "playlist_folder_template": "%(playlist_title)s",
                "numbering": False,
                "duplicate_action": "skip",
                "cookies_file": "",
                "rate_limit": "",
                "dry_run": False,
                "exit_on_complete": False,
                "sponsorblock": True,
                "reverse_playlist": False,
                "enable_sounds": True
            },
            "video": {
                "preferred_format": "mp4",
                "quality_priority": ["480", "360", "720"],
                "preferred_codec": "h264"
            },
            "audio": {
                "preferred_format": "m4a",
                "quality_priority": ["128", "192", "264"],
                "default_quality": 128
            },
            "subtitle": {
                "prefer_human": True,
                "language": "en",
                "preferred_format": "srt"
            }
        }

    def validate(self):
        errors = []
        g = self.config.get("general", {})
        if not isinstance(g.get("max_threads"), int) or g["max_threads"] < 1:
            errors.append("general.max_threads must be a positive integer")
        if not isinstance(g.get("timeout_seconds"), int) or g["timeout_seconds"] < 1:
            errors.append("general.timeout_seconds must be a positive integer")
        if g.get("default_format") not in ("video", "audio"):
            errors.append("general.default_format must be 'video' or 'audio'")
        if g.get("duplicate_action") not in ("skip", "overwrite", "keep"):
            errors.append("general.duplicate_action must be 'skip', 'overwrite', or 'keep'")
        if not isinstance(g.get("clear_temp"), bool):
            errors.append("general.clear_temp must be true/false")
        if not isinstance(g.get("numbering"), bool):
            errors.append("general.numbering must be true/false")
        if not isinstance(g.get("dry_run", False), bool):
            errors.append("general.dry_run must be true/false")
        if not isinstance(g.get("sponsorblock", True), bool):
            errors.append("general.sponsorblock must be true/false")
        if not isinstance(g.get("reverse_playlist", False), bool):
            errors.append("general.reverse_playlist must be true/false")
        if not isinstance(g.get("exit_on_complete", False), bool):
            errors.append("general.exit_on_complete must be true/false")
        if not isinstance(g.get("enable_sounds", True), bool):
            errors.append("general.enable_sounds must be true/false")
        v = self.config.get("video", {})
        if v.get("preferred_format") not in ("mp4", "mkv", "webm"):
            errors.append("video.preferred_format must be 'mp4', 'mkv', or 'webm'")
        if v.get("preferred_codec") not in ("h264", "h265", "vp9"):
            errors.append("video.preferred_codec must be 'h264', 'h265', or 'vp9'")
        if not isinstance(v.get("quality_priority"), list) or not v["quality_priority"]:
            errors.append("video.quality_priority must be a non-empty list")
        a = self.config.get("audio", {})
        if a.get("preferred_format") not in ("mp3", "m4a", "opus"):
            errors.append("audio.preferred_format must be 'mp3', 'm4a', or 'opus'")
        if not isinstance(a.get("quality_priority"), list) or not a["quality_priority"]:
            errors.append("audio.quality_priority must be a non-empty list")
        if not isinstance(a.get("default_quality"), int):
            errors.append("audio.default_quality must be an integer")
        s = self.config.get("subtitle", {})
        if not isinstance(s.get("language"), str) or len(s["language"]) < 2:
            errors.append("subtitle.language must be a valid language code (e.g. 'en')")
        if not isinstance(s.get("prefer_human"), bool):
            errors.append("subtitle.prefer_human must be true/false")
        if s.get("preferred_format") not in ("srt", "vtt", "ass"):
            errors.append("subtitle.preferred_format must be 'srt', 'vtt', or 'ass'")
        return errors

    def resolve_path(self, relative_path):
        return os.path.join(self.working_dir, relative_path)

    def __getitem__(self, key):
        return self.config[key]

    def __setitem__(self, key, value):
        self.config[key] = value

    def get(self, *args, **kwargs):
        return self.config.get(*args, **kwargs)
