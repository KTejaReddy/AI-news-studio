"""AssetLibrary for B-roll asset indexing, querying, importing, and deletion.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import uuid
from datetime import datetime

from PIL import Image, ImageDraw
import imageio

from core.broll.scene_asset import SceneAsset


class AssetLibrary:
    """Manages the index registry of B-roll media assets and handles file imports/deletions."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize the AssetLibrary.

        Args:
            workspace_dir: Path to the workspace directory.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.library_dir = self.workspace_dir / "assets" / "broll"
        self.library_file = self.library_dir / "library.json"
        self.imported_dir = self.library_dir / "imported"
        self.thumbnails_dir = self.library_dir / "thumbnails"

        # Create subfolders
        self.library_dir.mkdir(parents=True, exist_ok=True)
        self.imported_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger(self.__class__.__name__)
        self.assets: Dict[str, SceneAsset] = {}
        self.load_library()

    def load_library(self) -> None:
        """Load B-roll library entries from library.json."""
        if not self.library_file.exists():
            self.assets = {}
            return

        try:
            with open(self.library_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for asset_id, details in data.items():
                    self.assets[asset_id] = SceneAsset.from_dict(details)
            self._logger.info(f"Loaded {len(self.assets)} assets from B-roll library.")
        except Exception as e:
            self._logger.error(f"Failed to load B-roll library file: {e}")
            self.assets = {}

    def save_library(self) -> None:
        """Save B-roll library entries to library.json."""
        try:
            data = {asset_id: asset.to_dict() for asset_id, asset in self.assets.items()}
            with open(self.library_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self._logger.debug("B-roll library saved successfully.")
        except Exception as e:
            self._logger.error(f"Failed to save B-roll library: {e}")

    def add_asset(self, asset: SceneAsset) -> None:
        """Add or update an asset in the library.

        Args:
            asset: SceneAsset instance.
        """
        self.assets[asset.asset_id] = asset
        self.save_library()

    def get_asset(self, asset_id: str) -> Optional[SceneAsset]:
        """Retrieve an asset by its ID.

        Args:
            asset_id: Unique asset UUID.

        Returns:
            SceneAsset or None.
        """
        return self.assets.get(asset_id)

    def remove_asset(self, asset_id: str) -> bool:
        """Remove an asset from index registry and delete local file/thumbnail if exists.

        Args:
            asset_id: Unique asset UUID.

        Returns:
            True if deleted, False otherwise.
        """
        if asset_id not in self.assets:
            return False

        asset = self.assets[asset_id]
        
        # Try to delete associated media file
        if asset.file_path:
            file_path = Path(asset.file_path)
            if not file_path.is_absolute():
                file_path = self.workspace_dir / file_path
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                self._logger.warning(f"Could not delete media file {file_path}: {e}")

        # Try to delete thumbnail
        if asset.thumbnail_path:
            thumb_path = Path(asset.thumbnail_path)
            if not thumb_path.is_absolute():
                thumb_path = self.workspace_dir / thumb_path
            try:
                if thumb_path.exists():
                    thumb_path.unlink()
            except Exception as e:
                self._logger.warning(f"Could not delete thumbnail {thumb_path}: {e}")

        del self.assets[asset_id]
        self.save_library()
        self._logger.info(f"Asset {asset_id} removed from library.")
        return True

    def list_assets(self) -> List[SceneAsset]:
        """List all registered assets in the library.

        Returns:
            List of SceneAsset instances.
        """
        return list(self.assets.values())

    def generate_thumbnail(self, media_path: Path, asset_id: str, asset_type: str) -> str:
        """Generate a thumbnail image for a video or image file.

        Args:
            media_path: Absolute path to the source media file.
            asset_id: UUID of the asset.
            asset_type: Classification string ("Image", "Video", etc.)

        Returns:
            Relative path to the generated thumbnail file from workspace.
        """
        thumb_file = self.thumbnails_dir / f"{asset_id}.png"
        
        # Fallback default thumbnail generation (colored block with text) if fails
        def create_fallback(message: str) -> None:
            img = Image.new("RGB", (256, 256), color=(40, 44, 52))
            d = ImageDraw.Draw(img)
            # Add text or simple visual indicator
            d.rectangle([(10, 10), (246, 246)], outline=(70, 70, 70), width=3)
            d.text((30, 120), message, fill=(200, 200, 200))
            img.save(thumb_file)

        if not media_path.exists():
            create_fallback("Missing File")
            return str(thumb_file.relative_to(self.workspace_dir))

        try:
            # Determine how to read based on file suffix or asset_type
            ext = media_path.suffix.lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
                # Open with PIL
                with Image.open(media_path) as img:
                    img.thumbnail((256, 256))
                    # Convert to RGB if palette/RGBA for PNG
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    img.save(thumb_file, "PNG")
            elif ext in [".mp4", ".avi", ".mov", ".mkv", ".webm"]:
                # Open first frame using imageio
                reader = imageio.get_reader(str(media_path))
                frame = None
                for i, f in enumerate(reader):
                    if i == 0:
                        frame = f
                        break
                reader.close()

                if frame is not None:
                    img = Image.fromarray(frame)
                    img.thumbnail((256, 256))
                    img.save(thumb_file, "PNG")
                else:
                    create_fallback("Video Frame Error")
            else:
                create_fallback(f"Asset: {asset_type}")
        except Exception as e:
            self._logger.warning(f"Error generating thumbnail for {media_path}: {e}")
            create_fallback(f"Format: {ext.upper() if ext else 'Unknown'}")

        return str(thumb_file.relative_to(self.workspace_dir))

    def import_local_asset(
        self,
        source_path: Path,
        scene_id: str,
        prompt: str = "Imported B-Roll media",
        provider: str = "Local Import",
        asset_type: str = "Video",
        duration: float = 0.0,
        aspect_ratio: str = "16:9",
        tags: Optional[List[str]] = None
    ) -> SceneAsset:
        """Import a local file into the asset library.

        Args:
            source_path: Path to the local file to import.
            scene_id: Scenario sequence ID.
            prompt: Text prompt description.
            provider: Engine source name.
            asset_type: "Image", "Video", etc.
            duration: Asset runtime length.
            aspect_ratio: Configured aspect ratio.
            tags: Asset category list.

        Returns:
            The created and registered SceneAsset.
        """
        source_path = Path(source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Source file {source_path} does not exist.")

        asset_id = str(uuid.uuid4())
        dest_filename = f"{asset_id}{source_path.suffix}"
        dest_path = self.imported_dir / dest_filename

        # Copy the file
        shutil.copy2(source_path, dest_path)

        # Generate thumbnail
        rel_media_path = dest_path.relative_to(self.workspace_dir)
        thumb_rel_path = self.generate_thumbnail(dest_path, asset_id, asset_type)

        # Build asset
        asset = SceneAsset(
            asset_id=asset_id,
            scene_id=scene_id,
            prompt=prompt,
            provider=provider,
            file_path=str(rel_media_path),
            asset_type=asset_type,
            duration=duration,
            aspect_ratio=aspect_ratio,
            thumbnail_path=thumb_rel_path,
            tags=tags or ["imported"],
            status="completed"
        )

        self.add_asset(asset)
        self._logger.info(f"Imported local asset {asset_id} mapping to scene {scene_id}.")
        return asset
