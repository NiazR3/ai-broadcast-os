"""Input validation utilities for the Broadcast service."""

import re

# Stream keys are typically alphanumeric with hyphens, underscores, dots, tildes,
# and sometimes query parameters for tokens/authentication.
# Reject characters that could break the FFmpeg tee muxer syntax: | [ ] \ / newlines, control chars.
SAFE_STREAM_KEY_RE = re.compile(r"^[a-zA-Z0-9\-_.~?=&]+$")


def validate_stream_key(key: str) -> str:
    """Validate a stream key.

    Args:
        key: The stream key string to validate.

    Returns:
        The validated key (unchanged if valid).

    Raises:
        ValueError: If the key contains invalid characters or exceeds length limits.
    """
    if not key:
        return key  # Empty string means "not configured" -- valid.
    if len(key) > 512:
        raise ValueError("Stream key too long (max 512 characters)")
    if not SAFE_STREAM_KEY_RE.match(key):
        raise ValueError(
            "Stream key contains invalid characters. "
            "Only alphanumeric characters, hyphens, underscores, "
            "dots, tildes, and query parameter characters are allowed."
        )
    return key
