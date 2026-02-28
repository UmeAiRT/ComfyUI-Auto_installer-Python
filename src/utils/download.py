"""
File download utilities with aria2c acceleration and httpx fallback.

Replaces the PowerShell Save-File function from UmeAiRTUtils.psm1.
Adds SHA256 checksum verification (a security improvement over the original).
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import httpx
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from src.utils.logging import get_logger


def _find_aria2c() -> Path | None:
    """Locate aria2c executable on the system."""
    # Check common locations
    import os
    import sys

    candidates: list[Path] = []

    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            candidates.append(Path(local_app) / "aria2" / "aria2c.exe")

    # Check PATH
    which = shutil.which("aria2c")
    if which:
        candidates.insert(0, Path(which))

    for path in candidates:
        if path.exists():
            return path

    return None


def verify_checksum(file_path: Path, expected_sha256: str) -> bool:
    """
    Verify the SHA256 checksum of a downloaded file.

    Args:
        file_path: Path to the file to verify.
        expected_sha256: Expected SHA256 hex digest (lowercase).

    Returns:
        True if checksum matches, False otherwise.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest().lower() == expected_sha256.lower()


def _download_with_aria2c(
    url: str,
    dest: Path,
    aria2c_path: Path,
) -> bool:
    """
    Download using aria2c for maximum speed.

    Returns True on success, False on failure.
    """
    log = get_logger()

    args = [
        str(aria2c_path),
        "--console-log-level=warn",
        "--disable-ipv6",
        "--quiet=true",
        "-x", "16",
        "-s", "16",
        "-k", "1M",
        f"--dir={dest.parent}",
        f"--out={dest.name}",
        url,
    ]

    log.info(f"Using aria2c: {aria2c_path}")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
        )
        if result.returncode == 0:
            return True
        else:
            log.info(f"aria2c failed (code {result.returncode}): {result.stderr[:200]}")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        log.info(f"aria2c error: {e}")
        return False


def _download_with_httpx(url: str, dest: Path) -> None:
    """Download using httpx with a Rich progress bar."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))

        with Progress(
            TextColumn("[bold blue]{task.fields[filename]}"),
            BarColumn(bar_width=40),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            filename = dest.name
            if len(filename) > 40:
                filename = filename[:37] + "..."

            task = progress.add_task("download", filename=filename, total=total or None)

            with open(dest, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))


def download_file(
    url: str,
    dest: Path | str,
    *,
    checksum: str | None = None,
    force: bool = False,
) -> Path:
    """
    Download a file from a URL to a destination path.

    Tries aria2c first for speed, then falls back to httpx.
    Optionally verifies SHA256 checksum after download.

    Args:
        url: Source URL to download from.
        dest: Destination file path.
        checksum: Optional SHA256 hex digest for verification.
        force: If True, re-download even if file exists.

    Returns:
        Path to the downloaded file.

    Raises:
        RuntimeError: If download fails or checksum doesn't match.
    """
    dest = Path(dest)
    log = get_logger()

    # Skip if already exists (and no checksum to verify or checksum matches)
    if dest.exists() and not force:
        if checksum and not verify_checksum(dest, checksum):
            log.warning(f"Checksum mismatch for existing '{dest.name}', re-downloading...", level=2)
        else:
            log.sub(f"File '{dest.name}' already exists. Skipping download.", style="success")
            return dest

    log.sub(f"Downloading \"{url.split('/')[-1]}\"", style="debug")

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Try aria2c first
    aria2c = _find_aria2c()
    downloaded = False

    if aria2c:
        downloaded = _download_with_aria2c(url, dest, aria2c)
        if downloaded:
            log.info("Download successful (aria2c).")

    # Fallback to httpx
    if not downloaded:
        if aria2c:
            log.info("aria2c failed, falling back to httpx...")
        try:
            _download_with_httpx(url, dest)
            log.info("Download successful (httpx).")
        except (httpx.HTTPError, OSError) as e:
            raise RuntimeError(f"Download failed for '{url}': {e}") from e

    # Verify checksum
    if checksum:
        if not verify_checksum(dest, checksum):
            dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"Checksum verification failed for '{dest.name}'. "
                f"Expected: {checksum[:16]}... File has been deleted."
            )
        log.info("Checksum verified ✓")

    return dest
