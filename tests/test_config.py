import os
import json
import tempfile
from utils.config import Config


def _make_config(data):
    d = tempfile.mkdtemp()
    path = os.path.join(d, "config.json")
    os.makedirs(os.path.join(d, "config"), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)
    return Config(path)


def test_defaults():
    c = Config.__new__(Config)
    d = c.defaults()
    assert d["general"]["clear_temp"] == True
    assert d["general"]["enable_sounds"] == True
    assert d["paths"]["downloads_dir"] == "downloads"
    assert d["paths"]["temp_dir"] == "temp"
    assert d["network"]["timeout_seconds"] == 5
    assert d["network"]["proxy"] == ""
    assert d["download"]["default_format"] == "video"
    assert d["download"]["max_threads"] == 10


def test_validate_clean():
    c = _make_config({
        "download": {"max_threads": 3, "default_format": "video",
                     "duplicate_action": "skip", "archive_action": "skip", "numbering": False,
                     "filename_template": "%(title)s.%(ext)s", "playlist_folder_template": "%(playlist)s"},
        "network": {"timeout_seconds": 5, "cookies_file": ""},
        "paths": {"downloads_dir": "downloads", "temp_dir": "temp",
                  "archive_file": "a.txt", "log_file": "l.txt", "failed_file": "f.txt"},
        "general": {"clear_temp": True},
        "video": {"preferred_format": "mp4", "quality_priority": ["480", "360"], "preferred_codec": "h264"},
        "audio": {"preferred_format": "m4a", "quality_priority": ["128"], "default_quality": 128},
        "subtitle": {"prefer_human": True, "language": "en", "preferred_format": "srt"}
    })
    assert c.validate() == []


def test_validate_bad_format():
    c = _make_config({
        "download": {"max_threads": 3, "default_format": "gif",
                     "duplicate_action": "skip", "numbering": False},
        "network": {"timeout_seconds": 5, "cookies_file": ""},
        "general": {"clear_temp": True},
        "video": {"preferred_format": "mp4", "preferred_codec": "h264", "quality_priority": ["480"]},
        "audio": {"preferred_format": "m4a", "quality_priority": ["128"], "default_quality": 128},
        "subtitle": {"prefer_human": True, "language": "en", "preferred_format": "srt"}
    })
    errs = c.validate()
    assert any("default_format" in e for e in errs)


def test_validate_negative_threads():
    c = _make_config({
        "download": {"max_threads": -1, "default_format": "video",
                     "duplicate_action": "skip", "numbering": False},
        "network": {"timeout_seconds": 5, "cookies_file": ""},
        "general": {"clear_temp": True},
        "video": {"preferred_format": "mp4", "preferred_codec": "h264", "quality_priority": ["480"]},
        "audio": {"preferred_format": "m4a", "quality_priority": ["128"], "default_quality": 128},
        "subtitle": {"prefer_human": True, "language": "en", "preferred_format": "srt"}
    })
    errs = c.validate()
    assert any("max_threads" in e for e in errs)


def test_old_format_migration():
    c = _make_config({
        "general": {"max_threads": 3, "timeout_seconds": 5, "default_format": "video",
                     "duplicate_action": "skip", "clear_temp": True, "numbering": False,
                     "cookies_file": "", "downloads_dir": "downloads", "temp_dir": "temp",
                     "proxy": "socks5://127.0.0.1:1080",
                     "filename_template": "%(title)s.%(ext)s",
                     "playlist_folder_template": "%(playlist)s",
                     "enable_sounds": False, "exit_on_complete": True},
        "video": {"preferred_format": "mp4", "quality_priority": ["480", "360"], "preferred_codec": "h264"},
        "audio": {"preferred_format": "m4a", "quality_priority": ["128"], "default_quality": 128},
        "subtitle": {"prefer_human": True, "language": "en", "preferred_format": "srt"}
    })
    d = c.config
    assert d["general"]["clear_temp"] == True
    assert d["general"]["enable_sounds"] == False
    assert d["general"]["exit_on_complete"] == True
    assert d["network"]["proxy"] == "socks5://127.0.0.1:1080"
    assert d["network"]["timeout_seconds"] == 5
    assert d["paths"]["downloads_dir"] == "downloads"
    assert d["download"]["max_threads"] == 3
    assert d["download"]["default_format"] == "video"
    assert "timeout_seconds" not in d.get("general", {})
    assert c.validate() == []
