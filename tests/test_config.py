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
    assert d["general"]["default_format"] == "video"
    assert d["general"]["max_threads"] == 10

def test_validate_clean():
    c = _make_config({
        "general": {"max_threads": 3, "timeout_seconds": 5, "default_format": "video",
                     "duplicate_action": "skip", "archive_action": "skip", "clear_temp": True, "numbering": False,
                     "cookies_file": "", "downloads_dir": "downloads", "temp_dir": "temp",
                     "archive_file": "a.txt", "log_file": "l.txt", "failed_file": "f.txt",
                     "filename_template": "%(title)s.%(ext)s", "playlist_folder_template": "%(playlist)s"},
        "video": {"preferred_format": "mp4", "quality_priority": ["480", "360"], "preferred_codec": "h264"},
        "audio": {"preferred_format": "m4a", "quality_priority": ["128"], "default_quality": 128},
        "subtitle": {"prefer_human": True, "language": "en", "preferred_format": "srt"}
    })
    assert c.validate() == []

def test_validate_bad_format():
    c = _make_config({
        "general": {"max_threads": 3, "timeout_seconds": 5, "default_format": "gif",
                     "duplicate_action": "skip", "clear_temp": True, "numbering": False,
                     "cookies_file": ""},
        "video": {"preferred_format": "mp4", "preferred_codec": "h264", "quality_priority": ["480"]},
        "audio": {"preferred_format": "m4a", "quality_priority": ["128"], "default_quality": 128},
        "subtitle": {"prefer_human": True, "language": "en", "preferred_format": "srt"}
    })
    errs = c.validate()
    assert any("default_format" in e for e in errs)

def test_validate_negative_threads():
    c = _make_config({
        "general": {"max_threads": -1, "timeout_seconds": 5, "default_format": "video",
                     "duplicate_action": "skip", "clear_temp": True, "numbering": False,
                     "cookies_file": ""},
        "video": {"preferred_format": "mp4", "preferred_codec": "h264", "quality_priority": ["480"]},
        "audio": {"preferred_format": "m4a", "quality_priority": ["128"], "default_quality": 128},
        "subtitle": {"prefer_human": True, "language": "en", "preferred_format": "srt"}
    })
    errs = c.validate()
    assert any("max_threads" in e for e in errs)
