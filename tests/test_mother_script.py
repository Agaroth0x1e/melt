import os
import sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def mother(mocker):
    from mother_script import MotherScript
    config = mocker.MagicMock()
    config.resolve_path.side_effect = lambda p: p
    config.__getitem__.side_effect = lambda k: {"general": {}}[k]
    config.get.return_value = {}
    logger = mocker.MagicMock()
    archive = mocker.MagicMock()
    failed = mocker.MagicMock()
    cli = mocker.MagicMock()
    return MotherScript(config, logger, archive, failed, cli)


class TestSanitize:
    def test_removes_invalid_chars(self, mother):
        assert mother._sanitize("file:name?") == "filename"

    def test_strips_whitespace(self, mother):
        assert mother._sanitize("  hello  ") == "hello"

    def test_keeps_valid_name(self, mother):
        assert mother._sanitize("valid_name.mp4") == "valid_name.mp4"


class TestCleanError:
    def test_strips_ansi_codes(self, mother):
        assert mother._clean_error("\x1b[31mERROR\x1b[0m") == "ERROR"

    def test_passes_plain_text(self, mother):
        assert mother._clean_error("hello world") == "hello world"

    def test_handles_non_string(self, mother):
        assert mother._clean_error(123) == "123"


class TestParseRange:
    def test_single_number(self, mother):
        entries = ["a", "b", "c"]
        assert mother._parse_range("2", entries) == ["b"]

    def test_range(self, mother):
        entries = ["a", "b", "c", "d", "e"]
        assert mother._parse_range("2-4", entries) == ["b", "c", "d"]

    def test_mixed(self, mother):
        entries = ["a", "b", "c", "d", "e"]
        assert mother._parse_range("1,3-4", entries) == ["a", "c", "d"]

    def test_out_of_bounds(self, mother):
        entries = ["a", "b"]
        assert mother._parse_range("10", entries) == ["a", "b"]

    def test_invalid_returns_all(self, mother):
        entries = ["a", "b", "c"]
        assert mother._parse_range("abc", entries) == entries


class TestHandleDuplicatePath:
    def test_overwrite_returns_path(self, mother):
        assert mother._handle_duplicate_path("/x/y.mp4", "overwrite") == "/x/y.mp4"

    def test_skip_returns_path(self, mother):
        assert mother._handle_duplicate_path("/x/y.mp4", "skip") == "/x/y.mp4"

    def test_new_file_returns_path(self, mother, tmp_path):
        p = os.path.join(tmp_path, "new.mp4")
        assert mother._handle_duplicate_path(p, "keep") == p

    def test_keep_adds_counter(self, mother, tmp_path):
        p = os.path.join(tmp_path, "file.mp4")
        existing = os.path.join(tmp_path, "file_1.mp4")
        open(p, "w").close()
        open(existing, "w").close()
        result = mother._handle_duplicate_path(p, "keep")
        assert result == os.path.join(tmp_path, "file_2.mp4")
