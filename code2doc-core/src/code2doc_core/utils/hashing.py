from __future__ import annotations

import hashlib
from pathlib import Path

# BLAKE2b digest size for file/content hashing (16 bytes -> 32 hex chars).
_DIGEST_SIZE: int = 16


def compute_file_hash(file_path: Path) -> str:
    """Compute a BLAKE2b hex digest of the file at *file_path*.

    The file is read in binary mode in 64 KiB chunks so that large files
    do not need to be loaded entirely into memory.

    Parameters
    ----------
    file_path:
        Path to the file to hash.

    Returns
    -------
    str
        A 32-character hexadecimal string (BLAKE2b with 16-byte digest).
    """
    hasher = hashlib.blake2b(digest_size=_DIGEST_SIZE)
    with file_path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)  # 64 KiB
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_content_hash(content: str) -> str:
    """Compute a BLAKE2b hex digest of a string.

    The string is encoded as UTF-8 before hashing.

    Parameters
    ----------
    content:
        The string content to hash.

    Returns
    -------
    str
        A 32-character hexadecimal string (BLAKE2b with 16-byte digest).
    """
    hasher = hashlib.blake2b(digest_size=_DIGEST_SIZE)
    hasher.update(content.encode("utf-8"))
    return hasher.hexdigest()
