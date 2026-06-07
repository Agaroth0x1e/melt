import tempfile
from components.downloader import Downloader

class FakeConfig:
    def __init__(self):
        self.data = {
            "general": {},
            "network": {"cookies_file": "", "cookies_from_browser": ""},
            "download": {"filename_template": "%(title)s.%(ext)s", "merge_mode": False, "sponsorblock": True},
            "video": {"preferred_format": "mp4", "quality_priority": ["480", "360"], "preferred_codec": "h264"},
            "audio": {"preferred_format": "m4a", "quality_priority": ["128", "192"], "default_quality": 128},
            "subtitle": {"language": "en", "preferred_format": "srt"},
        }
    def __getitem__(self, k): return self.data[k]
    def get(self, *a, **kw): return self.data.get(*a, **kw)
    def resolve_path(self, p): return p

class FakeLogger:
    def info(self, m): pass
    def warn(self, m): pass
    def error(self, m): pass

def test_cookies_opts_empty():
    d = Downloader(FakeConfig(), FakeLogger())
    assert d._cookies_opts() == {}

def test_cookies_opts_with_file():
    cfg = FakeConfig()
    _, cf = tempfile.mkstemp()
    cfg.data["network"]["cookies_file"] = cf
    d = Downloader(cfg, FakeLogger())
    opts = d._cookies_opts()
    assert "cookiefile" in opts
    assert opts["cookiefile"] == cf

def test_video_format_string():
    d = Downloader(FakeConfig(), FakeLogger())
    fstr = d._video_format_string()
    assert "bestvideo" in fstr
    assert "bestaudio" in fstr

def test_audio_format_string():
    d = Downloader(FakeConfig(), FakeLogger())
    fstr = d._audio_format_string()
    assert "bestaudio" in fstr
