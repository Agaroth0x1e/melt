import os
import tempfile
from utils.archive import Archive

def test_is_downloaded_empty():
    with tempfile.TemporaryDirectory() as d:
        a = Archive(os.path.join(d, "archive.txt"))
        assert not a.is_downloaded("abc123")

def test_mark_and_check():
    with tempfile.TemporaryDirectory() as d:
        a = Archive(os.path.join(d, "archive.txt"))
        a.mark_downloaded("abc123")
        assert a.is_downloaded("abc123")
        assert not a.is_downloaded("xyz789")

def test_multiple_ids():
    with tempfile.TemporaryDirectory() as d:
        a = Archive(os.path.join(d, "archive.txt"))
        for vid in ["a", "b", "c"]:
            a.mark_downloaded(vid)
        assert a.is_downloaded("a")
        assert a.is_downloaded("b")
        assert a.is_downloaded("c")
        assert not a.is_downloaded("d")

def test_persistence():
    path = os.path.join(tempfile.gettempdir(), "_test_archive.txt")
    try:
        a = Archive(path)
        a.mark_downloaded("persist-test")
        b = Archive(path)
        assert b.is_downloaded("persist-test")
    finally:
        if os.path.exists(path):
            os.remove(path)
