"""Tests for input sanitization utilities."""

import pytest
from utils.sanitization import sanitize_filename


class TestSanitizeFilename:
    """Test cases for sanitize_filename function."""

    def test_basic_filename(self):
        """Should pass through normal filenames unchanged."""
        assert sanitize_filename("document.pdf") == "document.pdf"
        assert sanitize_filename("my-file_v2.txt") == "my-file_v2.txt"

    def test_none_input(self):
        """Should return 'unknown' for None input."""
        assert sanitize_filename(None) == "unknown"

    def test_empty_string(self):
        """Should return 'unknown' for empty string."""
        assert sanitize_filename("") == "unknown"

    def test_path_traversal_unix(self):
        """Should prevent unix-style path traversal attacks."""
        assert sanitize_filename("../../../etc/passwd") == "passwd"
        assert sanitize_filename("foo/../bar/file.txt") == "file.txt"

    def test_path_traversal_windows(self):
        """Should prevent windows-style path traversal attacks."""
        assert sanitize_filename("..\\..\\windows\\system32") == "system32"
        assert sanitize_filename("C:\\Users\\admin\\file.txt") == "file.txt"

    def test_parent_directory_references(self):
        """Should remove .. sequences."""
        assert ".." not in sanitize_filename("file..name.txt")
        assert ".." not in sanitize_filename("..file.txt")

    def test_control_characters(self):
        """Should remove control characters to prevent log injection."""
        # Newlines
        assert sanitize_filename("file\nname.txt") == "filename.txt"
        assert sanitize_filename("file\r\nname.txt") == "filename.txt"
        # Null byte
        assert sanitize_filename("file\x00name.txt") == "filename.txt"
        # Other control chars
        assert sanitize_filename("file\x1fname.txt") == "filename.txt"

    def test_max_length_no_extension(self):
        """Should truncate long filenames without extension."""
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        assert len(result) == 255
        assert result == "a" * 255

    def test_max_length_with_extension(self):
        """Should preserve extension when truncating."""
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) == 255
        assert result.endswith(".pdf")

    def test_custom_max_length(self):
        """Should respect custom max_length parameter."""
        result = sanitize_filename("a" * 100, max_length=50)
        assert len(result) == 50

    def test_very_long_extension(self):
        """Should truncate very long extensions."""
        long_ext = "a" * 50 + "." + "x" * 50
        result = sanitize_filename(long_ext, max_length=30)
        # Extension limited to 10 chars
        assert len(result) <= 30

    def test_only_path_separators(self):
        """Should return 'unknown' if only path separators provided."""
        assert sanitize_filename("/") == "unknown"
        assert sanitize_filename("///") == "unknown"

    def test_mixed_separators(self):
        """Should handle mixed path separators."""
        assert sanitize_filename("path/to\\file.txt") == "file.txt"

    def test_unicode_filenames(self):
        """Should allow unicode characters in filenames."""
        assert sanitize_filename("文档.pdf") == "文档.pdf"
        assert sanitize_filename("résumé.doc") == "résumé.doc"

    def test_spaces_in_filename(self):
        """Should preserve spaces in filenames."""
        assert sanitize_filename("my document.pdf") == "my document.pdf"
