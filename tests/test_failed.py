import os
import tempfile
from utils.failed import FailedTracker

def test_record_writes_file():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "failed.txt")
        f = FailedTracker(path)
        info = {"title": "Test", "id": "abc", "url": "https://youtube.com/watch?v=abc", "playlist": "N/A", "destination": d}
        f.record(info, "Something went wrong")
        assert os.path.exists(path)
        content = open(path, encoding="utf-8").read()
        assert "Test" in content
        assert "abc" in content
        assert "Something went wrong" in content

def test_multiple_records():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "failed.txt")
        f = FailedTracker(path)
        for i in range(3):
            f.record({"title": f"Video {i}", "id": f"id{i}", "url": f"url{i}", "playlist": "N/A", "destination": d}, f"Error {i}")
        content = open(path, encoding="utf-8").read()
        assert content.count("Video 0") == 1
        assert content.count("Video 1") == 1
        assert content.count("Video 2") == 1
        assert content.count("============================================================") == 6
