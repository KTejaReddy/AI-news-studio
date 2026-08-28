"""AssetCache for caching prompt-to-file paths under cache/broll/ to avoid redundant generation calls.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Optional


class AssetCache:
    """Manages local visual asset caching using cryptographic hashing of prompt parameters."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize the AssetCache.

        Args:
            workspace_dir: Path to the workspace directory.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.cache_dir = self.workspace_dir / "cache" / "broll"
        self.cache_index_file = self.cache_dir / "cache_index.json"

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger(self.__class__.__name__)
        self.cache_registry: Dict[str, str] = {}
        self.load_cache_index()

    def _get_cache_key(self, prompt: str, provider: str, aspect_ratio: str, duration: float) -> str:
        """Generate a stable hash key from the input parameters.

        Args:
            prompt: Text prompt used.
            provider: Service provider name.
            aspect_ratio: Configured aspect ratio.
            duration: Asset runtime length.

        Returns:
            Hex string MD5 hash.
        """
        raw_key = f"{prompt.strip()}_{provider.strip()}_{aspect_ratio.strip()}_{duration:.2f}"
        return hashlib.md5(raw_key.encode("utf-8")).hexdigest()

    def load_cache_index(self) -> None:
        """Load cache entries from cache_index.json."""
        if not self.cache_index_file.exists():
            self.cache_registry = {}
            return

        try:
            with open(self.cache_index_file, "r", encoding="utf-8") as f:
                self.cache_registry = json.load(f)
            self._logger.info(f"Loaded {len(self.cache_registry)} cache index entries.")
        except Exception as e:
            self._logger.error(f"Failed to load cache index: {e}")
            self.cache_registry = {}

    def save_cache_index(self) -> None:
        """Save cache registry to disk."""
        try:
            with open(self.cache_index_file, "w", encoding="utf-8") as f:
                json.dump(self.cache_registry, f, indent=4)
        except Exception as e:
            self._logger.error(f"Failed to save cache index: {e}")

    def get_cached_asset_path(self, prompt: str, provider: str, aspect_ratio: str, duration: float) -> Optional[Path]:
        """Verify if a matching generated asset exists in cache.

        Args:
            prompt: Text prompt description.
            provider: Service provider name.
            aspect_ratio: Configured aspect ratio.
            duration: Asset duration.

        Returns:
            Absolute Path to cached media file or None.
        """
        key = self._get_cache_key(prompt, provider, aspect_ratio, duration)
        if key not in self.cache_registry:
            return None

        rel_path = self.cache_registry[key]
        abs_path = self.workspace_dir / rel_path

        if abs_path.exists():
            self._logger.info(f"Cache HIT for key {key} -> {abs_path}")
            return abs_path
        else:
            # File deleted externally, clean up registry
            self._logger.debug(f"Cache registry references missing file {abs_path}. Cleaning registry.")
            del self.cache_registry[key]
            self.save_cache_index()
            return None

    def add_to_cache(self, prompt: str, provider: str, aspect_ratio: str, duration: float, source_file: Path) -> Path:
        """Copy a generated file into the cache folder and index it.

        Args:
            prompt: Text prompt description.
            provider: Service provider name.
            aspect_ratio: Configured aspect ratio.
            duration: Visual clip duration.
            source_file: Current path of generated file to cache.

        Returns:
            The Path inside the cache folder.
        """
        if not source_file.exists():
            raise FileNotFoundError(f"Source file {source_file} not found; cannot cache.")

        key = self._get_cache_key(prompt, provider, aspect_ratio, duration)
        dest_filename = f"{key}{source_file.suffix}"
        dest_path = self.cache_dir / dest_filename

        try:
            # If it's already in the cache directory, just update index
            if source_file.resolve() != dest_path.resolve():
                import shutil
                shutil.copy2(source_file, dest_path)
            
            # Store relative path
            rel_dest = dest_path.relative_to(self.workspace_dir)
            self.cache_registry[key] = str(rel_dest)
            self.save_cache_index()
            self._logger.info(f"Cached asset written to {dest_path}")
            return dest_path
        except Exception as e:
            self._logger.error(f"Failed to copy file to cache: {e}")
            return source_file

    def clear_cache(self) -> None:
        """Delete all cached files and reset the registry."""
        for rel_path in self.cache_registry.values():
            abs_path = self.workspace_dir / rel_path
            try:
                if abs_path.exists():
                    abs_path.unlink()
            except Exception as e:
                self._logger.warning(f"Failed to delete cached file {abs_path}: {e}")

        self.cache_registry = {}
        if self.cache_index_file.exists():
            try:
                self.cache_index_file.unlink()
            except Exception as e:
                self._logger.error(f"Failed to delete cache index file: {e}")
        self._logger.info("B-roll cache cleared.")
