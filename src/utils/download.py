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
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from src.utils.logging import InstallerLogger


def _find_aria2c(aria2c_hint: Path | None = None) -> Path | None:
    """
    Locate aria2c executable using a 3-tier search strategy.

    1. System PATH (user-installed or package-manager-installed)
    2. aria2c_hint directory (e.g. install_path/scripts/aria2/)
    3. Package-relative scripts/aria2/ (if running from source)

    Args:
        aria2c_hint: Optional directory to search for aria2c.
    """
    import sys

    # 1. System PATH
    which = shutil.which("aria2c")
    if which:
        return Path(which)

    exe_name = "aria2c.exe" if sys.platform == "win32" else "aria2c"

    # 2. Hint directory (passed by caller, e.g. install_path/scripts/aria2/)
    if aria2c_hint is not None:
        candidate = aria2c_hint / exe_name
        if candidate.exists():
            return candidate

    # 3. Package-relative (running from source checkout)
    package_root = Path(__file__).resolve().parent.parent.parent
    candidate = package_root / "scripts" / "aria2" / exe_name
    if candidate.exists():
        return candidate

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
    *,
    quiet: bool = True,
    log: InstallerLogger | None = None,
) -> bool:
    """
    Download using aria2c for maximum speed.

    Returns True on success, False on failure.
    """
    if log is None:
        log = get_logger()

    args = [
        str(aria2c_path),
        "--console-log-level=warn",
        "--summary-interval=0",
        "--show-console-readout=true",
        "--continue=true",
        "--auto-file-renaming=false",
        "--disable-ipv6",
        "-x", "16",
        "-s", "16",
        "-k", "1M",
        f"--dir={dest.parent}",
        f"--out={dest.name}",
        url,
    ]

    log.info(f"Using aria2c: {aria2c_path}")

    try:
        result = subprocess.run(  # returncode checked below
            args,
            timeout=3600,  # 1 hour timeout
            capture_output=quiet,
        )
        if result.returncode == 0:
            return True
        else:
            log.info(f"aria2c failed (code {result.returncode})")
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
    url: str | list[str],
    dest: Path | str,
    *,
    checksum: str | None = None,
    force: bool = False,
    quiet: bool = True,
    aria2c_hint: Path | None = None,
    log: InstallerLogger | None = None,
) -> Path:
    """
    Download a file from one or more URLs to a destination path.

    When *url* is a list, each URL is tried in order — the first successful
    download wins.  This enables transparent HuggingFace → ModelScope failover.

    Tries aria2c first for speed, then falls back to httpx.
    Optionally verifies SHA256 checksum after download.

    Args:
        url: Source URL(s) to download from. Pass a list for multi-source
            fallback (e.g. ``[hf_url, ms_url]``).
        dest: Destination file path.
        checksum: Optional SHA256 hex digest for verification.
        force: If True, re-download even if file exists.
        quiet: If True (default), suppress aria2c console output.
        aria2c_hint: Optional directory where aria2c may be found
            (e.g. ``install_path / "scripts" / "aria2"``).

    Returns:
        Path to the downloaded file.

    Raises:
        RuntimeError: If all URLs fail or checksum doesn't match.
    """
    dest = Path(dest)
    if log is None:
        log = get_logger()

    # Normalise to list
    urls: list[str] = [url] if isinstance(url, str) else list(url)
    if not urls:
        raise RuntimeError("download_file: no URL provided.")

    # Skip if already exists (and no checksum to verify or checksum matches)
    aria2_control = dest.with_suffix(dest.suffix + ".aria2")
    if dest.exists() and not force:
        # If an aria2 control file exists, the previous download was interrupted
        if aria2_control.exists():
            log.warning(f"Incomplete download detected for '{dest.name}', resuming...", level=2)
        elif checksum and not verify_checksum(dest, checksum):
            log.warning(f"Checksum mismatch for existing '{dest.name}', re-downloading...", level=2)
        else:
            log.sub(f"'{dest.name}' already exists, skipping.", style="success")
            return dest

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Try each URL in order
    last_error: Exception | None = None
    for i, source_url in enumerate(urls):
        source_label = source_url.split("/")[2] if "/" in source_url else "unknown"
        if i > 0:
            log.info(f"Trying fallback source ({source_label})...")

        log.sub(f"Downloading \"{source_url.split('/')[-1]}\"", style="debug")

        try:
            # Try aria2c first
            aria2c = _find_aria2c(aria2c_hint)
            downloaded = False

            if aria2c:
                downloaded = _download_with_aria2c(source_url, dest, aria2c, quiet=quiet)
                if downloaded:
                    log.info("Download successful (aria2c).")

            # Fallback to httpx
            if not downloaded:
                if aria2c:
                    log.info("aria2c failed, falling back to httpx...")
                _download_with_httpx(source_url, dest)
                log.info("Download successful (httpx).")

            # If we got here, download succeeded — break out
            last_error = None
            break

        except (httpx.HTTPError, OSError, RuntimeError) as e:
            last_error = e
            log.info(f"Source {source_label} failed: {e}")
            # Clean up partial file before trying next source
            dest.unlink(missing_ok=True)
            continue

    if last_error is not None:
        raise RuntimeError(
            f"Download failed for '{dest.name}' from all {len(urls)} source(s): {last_error}"
        ) from last_error

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

