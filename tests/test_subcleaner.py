import os
import tempfile
from components.subcleaner import SubCleaner

class FakeLogger:
    def info(self, msg): pass
    def warn(self, msg): pass
    def error(self, msg): pass

def _write_srt(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def test_clean_removes_rollup():
    sc = SubCleaner(FakeLogger())
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tmp:
        path = tmp.name
    try:
        _write_srt(path, [
            "1",
            "00:00:01,000 --> 00:00:05,000",
            "Hello world",
            "",
            "2",
            "00:00:04,000 --> 00:00:08,000",
            "Hello world",
            "How are you",
            "",
            "3",
            "00:00:07,000 --> 00:00:10,000",
            "How are you",
            "I'm fine thanks",
            "",
        ])
        out = sc.clean_subtitle_file(path)
        content = _read(out)
        assert "Hello world" in content
        assert "How are you" in content
        assert "I'm fine thanks" in content
    finally:
        for p in [path, path.replace(".srt", ".clean.srt")]:
            if os.path.exists(p):
                os.remove(p)

def test_no_clean_if_no_rollup():
    sc = SubCleaner(FakeLogger())
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tmp:
        path = tmp.name
    try:
        _write_srt(path, [
            "1",
            "00:00:01,000 --> 00:00:05,000",
            "Hello world",
            "",
            "2",
            "00:00:06,000 --> 00:00:10,000",
            "Goodbye world",
            "",
        ])
        out = sc.clean_subtitle_file(path)
        content = _read(out)
        assert "Hello world" in content
        assert "Goodbye world" in content
    finally:
        for p in [path, path.replace(".srt", ".clean.srt")]:
            if os.path.exists(p):
                os.remove(p)
