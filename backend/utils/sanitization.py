"""Input sanitization utilities."""

import re


def sanitize_filename(filename: str | None, max_length: int = 255) -> str:
    """Sanitize a user-provided filename for safe logging and storage.

    Prevents:
    - Path traversal attacks (../, etc.)
    - Log injection (newlines, control characters)
    - Excessively long filenames

    Args:
        filename: The raw filename from user input
        max_length: Maximum allowed filename length

    Returns:
        A safe filename string
    """
    if not filename:
        return "unknown"

    # Remove path separators and parent directory references
    safe_name = filename.replace("\\", "/")  # Normalize separators
    safe_name = safe_name.split("/")[-1]  # Take only the filename part
    safe_name = safe_name.replace("..", "")  # Remove parent directory references

    # Remove control characters and newlines (prevent log injection)
    safe_name = re.sub(r"[\x00-\x1f\x7f-\x9f\n\r]", "", safe_name)

    # Limit length
    if len(safe_name) > max_length:
        # Preserve extension if present
        if "." in safe_name:
            name, ext = safe_name.rsplit(".", 1)
            ext = ext[:10]  # Limit extension length
            safe_name = name[: max_length - len(ext) - 1] + "." + ext
        else:
            safe_name = safe_name[:max_length]

    return safe_name or "unknown"
