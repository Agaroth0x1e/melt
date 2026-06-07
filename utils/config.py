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

    def _deep_merge(self, base, overlay):
        changed = False
        for key, value in overlay.items():
            if key not in base:
                base[key] = value
                changed = True
            elif isinstance(value, dict) and isinstance(base.get(key), dict):
                if self._deep_merge(base[key], value):
                    changed = True
        return changed

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            changed = self._deep_merge(loaded, self.defaults())
            if changed:
                self.config = loaded
                self.save()
            return loaded

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
                "archive_file": "logs/archive.txt",
                "log_file": "logs/log.txt",
                "failed_file": "logs/failed.txt",
                "skipped_file": "logs/skipped.txt",
                "clear_temp": True,
                "default_format": "video",
                "max_threads": 10,
                "timeout_seconds": 5,
                "filename_template": "%(title)s.%(ext)s",
                "playlist_folder_template": "%(playlist_title)s",
                "numbering": False,
                "duplicate_action": "skip",
                "archive_action": "skip",
                "archive_timeout": 10,
                "cookies_file": "",
                "cookies_from_browser": "",
                "rate_limit": "",
                "exit_on_complete": False,
                "sponsorblock": True,
                "reverse_playlist": False,
                "enable_sounds": True,
                "default_reuse": True,
                "format_preview": False,
                "merge_mode": False,
                "extract_flat": {
                    "inspect": True,
                    "search": False
                },
                "proxy": ""
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
            },
            "watch_folder": {
                "enabled": False,
                "path": "watch",
                "interval_seconds": 60,
                "auto_delete": True,
                "default_format": "video",
                "default_dest": "downloads",
            },
            "search": {
                "filter_type": "all",
                "default_sort": "relevance"
            },
            "chapter_splitter": {
                "enabled": False,
                "output_template": "%(title)s - %(chapter)s.%(ext)s"
            },
            "sounds": {
                "batch_start": "",
                "analyze_complete": "",
                "download_error": "",
                "aborting": "",
                "fatal_error": "",
                "completion": ""
            }
        }

    def validate(self):
        errors = []
        g = self.config.get("general", {})
        if not isinstance(g.get("max_threads"), int) or g["max_threads"] < 1:
            errors.append("general.max_threads must be a positive integer")
        if not isinstance(g.get("timeout_seconds"), int) or g["timeout_seconds"] < -1 or g["timeout_seconds"] == 0:
            errors.append("general.timeout_seconds must be a positive integer, or -1 for no timeout")
        if g.get("default_format") not in ("video", "audio"):
            errors.append("general.default_format must be 'video' or 'audio'")
        if g.get("duplicate_action") not in ("skip", "overwrite", "keep"):
            errors.append("general.duplicate_action must be 'skip', 'overwrite', or 'keep'")
        archive_action = g.get("archive_action")
        if archive_action is not None and archive_action not in ("skip", "ask", "redownload"):
            errors.append("general.archive_action must be 'skip', 'ask', or 'redownload'")
        archive_timeout = g.get("archive_timeout")
        if archive_timeout is not None and (not isinstance(archive_timeout, int) or archive_timeout < 1):
            errors.append("general.archive_timeout must be a positive integer")
        if not isinstance(g.get("clear_temp"), bool):
            errors.append("general.clear_temp must be true/false")
        if not isinstance(g.get("numbering"), bool):
            errors.append("general.numbering must be true/false")
        if not isinstance(g.get("sponsorblock", True), bool):
            errors.append("general.sponsorblock must be true/false")
        if not isinstance(g.get("reverse_playlist", False), bool):
            errors.append("general.reverse_playlist must be true/false")
        if not isinstance(g.get("exit_on_complete", False), bool):
            errors.append("general.exit_on_complete must be true/false")
        if not isinstance(g.get("enable_sounds", True), bool):
            errors.append("general.enable_sounds must be true/false")
        if not isinstance(g.get("default_reuse", True), bool):
            errors.append("general.default_reuse must be true/false")
        if not isinstance(g.get("format_preview", False), bool):
            errors.append("general.format_preview must be true/false")
        if not isinstance(g.get("merge_mode", False), bool):
            errors.append("general.merge_mode must be true/false")
        ef = g.get("extract_flat", {})
        if not isinstance(ef, dict):
            errors.append("general.extract_flat must be an object")
        else:
            if not isinstance(ef.get("inspect", True), bool):
                errors.append("general.extract_flat.inspect must be true/false")
            if not isinstance(ef.get("search", False), bool):
                errors.append("general.extract_flat.search must be true/false")
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
        sc = self.config.get("search", {})
        if sc.get("filter_type") not in ("all", "video", "playlist", None):
            errors.append("search.filter_type must be 'all', 'video', or 'playlist'")
        if sc.get("default_sort") not in ("relevance", "views", "date", "duration", None):
            errors.append("search.default_sort must be 'relevance', 'views', 'date', or 'duration'")
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
