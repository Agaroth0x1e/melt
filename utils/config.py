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

    def _migrate(self, cfg):
        changes = False
        general = cfg.get('general', {})
        if not general:
            return cfg, changes

        sections = {
                'paths': ['temp_dir', 'downloads_dir', 'archive_file', 'log_file', 'failed_file', 'skipped_file'],
            'network': ['proxy', 'rate_limit', 'cookies_file', 'cookies_from_browser', 'timeout_seconds'],
            'download': ['default_format', 'max_threads', 'filename_template', 'playlist_folder_template',
                         'numbering', 'duplicate_action', 'archive_action', 'archive_timeout',
                         'sponsorblock', 'reverse_playlist', 'format_preview', 'merge_mode', 'extract_flat'],
        }

        for section, keys in sections.items():
            if section not in cfg:
                cfg[section] = {}
                changes = True
            for k in keys:
                if k in general and k not in cfg[section]:
                    cfg[section][k] = general[k]
                    changes = True

        if 'warp' in general and 'warp' not in cfg.get('network', {}):
            cfg.setdefault('network', {})['warp'] = general['warp'] in ('auto', True, 'true', 'on')
            changes = True

        keep = ['clear_temp', 'exit_on_complete', 'enable_sounds', 'default_reuse', 'dry_run', 'prompt_timeout']
        new_general = {}
        for k in keep:
            if k in general:
                new_general[k] = general[k]
        if new_general:
            cfg['general'] = new_general
        elif 'general' in cfg:
            del cfg['general']
            changes = True
        return cfg, changes

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            migrated, changed = self._migrate(loaded)
            if changed:
                loaded = migrated
            changed2 = self._deep_merge(loaded, self.defaults())
            if changed or changed2:
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
                "clear_temp": True,
                "exit_on_complete": False,
                "enable_sounds": True,
                "default_reuse": True,
                "prompt_timeout": 30,
            },
            "paths": {
                "temp_dir": "temp",
                "downloads_dir": "downloads",
                "archive_file": "logs/archive.txt",
                "log_file": "logs/log.txt",
                "failed_file": "logs/failed.txt",
                "skipped_file": "logs/skipped.txt",
            },
            "network": {
                "proxy": "",
                "warp": False,
                "rate_limit": "",
                "cookies_file": "",
                "cookies_from_browser": "",
                "timeout_seconds": 5,
            },
            "download": {
                "default_format": "video",
                "max_threads": 10,
                "filename_template": "%(title)s.%(ext)s",
                "playlist_folder_template": "%(playlist_title)s",
                "numbering": False,
                "duplicate_action": "skip",
                "archive_action": "skip",
                "archive_timeout": 10,
                "sponsorblock": True,
                "reverse_playlist": False,
                "format_preview": False,
                "merge_mode": False,
                "extract_flat": {
                    "inspect": True,
                    "search": False
                },
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
                "preferred_format": "srt",
                "transliterate": ""
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
        n = self.config.get("network", {})
        d = self.config.get("download", {})
        p = self.config.get("paths", {})

        if not isinstance(d.get("max_threads"), int) or d["max_threads"] < 1:
            errors.append("download.max_threads must be a positive integer")
        if not isinstance(n.get("timeout_seconds"), int) or n["timeout_seconds"] < -1 or n["timeout_seconds"] == 0:
            errors.append("network.timeout_seconds must be a positive integer, or -1 for no timeout")
        if d.get("default_format") not in ("video", "audio"):
            errors.append("download.default_format must be 'video' or 'audio'")
        if d.get("duplicate_action") not in ("skip", "overwrite", "keep"):
            errors.append("download.duplicate_action must be 'skip', 'overwrite', or 'keep'")
        archive_action = d.get("archive_action")
        if archive_action is not None and archive_action not in ("skip", "ask", "redownload"):
            errors.append("download.archive_action must be 'skip', 'ask', or 'redownload'")
        archive_timeout = d.get("archive_timeout")
        if archive_timeout is not None and (not isinstance(archive_timeout, int) or archive_timeout < 1):
            errors.append("download.archive_timeout must be a positive integer")
        if not isinstance(g.get("clear_temp"), bool):
            errors.append("general.clear_temp must be true/false")
        if not isinstance(d.get("numbering"), bool):
            errors.append("download.numbering must be true/false")
        if not isinstance(d.get("sponsorblock", True), bool):
            errors.append("download.sponsorblock must be true/false")
        if not isinstance(d.get("reverse_playlist", False), bool):
            errors.append("download.reverse_playlist must be true/false")
        if not isinstance(g.get("exit_on_complete", False), bool):
            errors.append("general.exit_on_complete must be true/false")
        if not isinstance(g.get("enable_sounds", True), bool):
            errors.append("general.enable_sounds must be true/false")
        if not isinstance(g.get("default_reuse", True), bool):
            errors.append("general.default_reuse must be true/false")
        prompt_timeout = g.get("prompt_timeout", 30)
        if not isinstance(prompt_timeout, int) or prompt_timeout < -1 or prompt_timeout == 0:
            errors.append("general.prompt_timeout must be a positive integer, or -1 for no timeout")
        if not isinstance(d.get("format_preview", False), bool):
            errors.append("download.format_preview must be true/false")
        if not isinstance(d.get("merge_mode", False), bool):
            errors.append("download.merge_mode must be true/false")
        ef = d.get("extract_flat", {})
        if not isinstance(ef, dict):
            errors.append("download.extract_flat must be an object")
        else:
            if not isinstance(ef.get("inspect", True), bool):
                errors.append("download.extract_flat.inspect must be true/false")
            if not isinstance(ef.get("search", False), bool):
                errors.append("download.extract_flat.search must be true/false")
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
