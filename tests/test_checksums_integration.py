"""
Integration tests for validating external URLs and checksums.
These tests make actual network requests and download large files.
Run via `pytest -m integration`
"""

import hashlib
import json
from pathlib import Path

import httpx
import pytest

# Load dependencies.json
DEPENDENCIES_FILE = Path(__file__).parent.parent / "scripts" / "dependencies.json"


def load_urls_to_test() -> list[tuple[str, str, str]]:
    """
    Returns a list of tuples: (friendly_name, url, expected_sha256)
    Excludes tools like aria2c where we only track version, not URL.
    """
    if not DEPENDENCIES_FILE.exists():
        return []

    with open(DEPENDENCIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    urls = []

    # Check wheels
    if "pip_packages" in data and "wheels" in data["pip_packages"]:
        for wheel in data["pip_packages"]["wheels"]:
            name = wheel.get("name", "unknown")
            versions = wheel.get("versions", {})
            checksums = wheel.get("checksums", {})
            
            for key, url in versions.items():
                sha = checksums.get(key)
                if url and sha:
                    urls.append((f"{name}_{key}", url, sha))

    # Check tools (Git, aria2c, etc.) that have SHA-256
    if "tools" in data:
        for tool_name, tool_data in data["tools"].items():
            url = tool_data.get("url")
            sha = tool_data.get("sha256")
            if url and sha:
                urls.append((tool_name, url, sha))
    
    return urls


URLS_TEST_DATA = load_urls_to_test()


@pytest.mark.integration
@pytest.mark.parametrize("name, url, expected_sha256", URLS_TEST_DATA)
def test_download_checksum(name: str, url: str, expected_sha256: str) -> None:
    """
    Downloads the file at `url` into memory or a tempfile and verifies its SHA-256.
    Uses httpx stream to calculate the hash efficiently without loading the entire file into memory at once.
    """
    sha256 = hashlib.sha256()

    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes(chunk_size=8192):
                sha256.update(chunk)

    actual_sha256 = sha256.hexdigest().lower()
    expected_val = expected_sha256.lower()

    assert actual_sha256 == expected_val, f"Checksum mismatch for {name} ({url}). Expected {expected_val}, got {actual_sha256}"
