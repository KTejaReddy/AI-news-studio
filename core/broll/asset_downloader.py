"""AssetDownloader for downloading assets from remote URLs or copying simulated media files.
"""

import logging
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional


class AssetDownloader:
    """Helper class to fetch files from HTTP(S) URLs or copy local files, reporting progress."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)

    def download_file(
        self,
        url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> bool:
        """Download or copy a file to dest_path, invoking progress_callback with float from 0 to 1.

        Args:
            url: Remote URL string or local file path string.
            dest_path: Location to write the file.
            progress_callback: Optional function receiving progress float.

        Returns:
            True if download succeeded, False otherwise.
        """
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Local file path copy simulation
        if not url.startswith(("http://", "https://")):
            src_path = Path(url)
            if not src_path.exists():
                self._logger.error(f"Source file not found for local copy: {url}")
                return False

            try:
                # Simulate a fast copy with progress reports
                total_size = src_path.stat().st_size
                block_size = max(1024 * 1024, total_size // 10)  # 10% blocks or 1MB
                bytes_copied = 0

                with open(src_path, "rb") as fsrc:
                    with open(dest_path, "wb") as fdest:
                        while True:
                            buf = fsrc.read(block_size)
                            if not buf:
                                break
                            fdest.write(buf)
                            bytes_copied += len(buf)
                            if progress_callback and total_size > 0:
                                progress_callback(min(1.0, bytes_copied / total_size))
                            time.sleep(0.02)  # subtle pacing

                if progress_callback:
                    progress_callback(1.0)
                self._logger.info(f"Local copy finished: {url} -> {dest_path}")
                return True
            except Exception as e:
                self._logger.error(f"Failed to copy local file: {e}")
                return False

        # 2. Remote HTTP/S URL download
        try:
            self._logger.info(f"Downloading remote file: {url} -> {dest_path}")
            
            # Use urllib.request with a custom block reader to track progress
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )

            with urllib.request.urlopen(req) as response:
                content_length = response.headers.get("Content-Length")
                total_size = int(content_length) if content_length is not None else 0
                bytes_downloaded = 0
                block_size = 8192

                with open(dest_path, "wb") as fdest:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        fdest.write(buffer)
                        bytes_downloaded += len(buffer)
                        
                        if progress_callback and total_size > 0:
                            progress_callback(min(0.99, bytes_downloaded / total_size))

            if progress_callback:
                progress_callback(1.0)
            self._logger.info(f"Download completed successfully.")
            return True

        except Exception as e:
            self._logger.error(f"Failed to download remote file from {url}: {e}")
            # Clean up partial downloads
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass
            return False
