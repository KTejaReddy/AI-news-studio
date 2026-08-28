"""ThumbnailGenerator for extracting PNG thumbnails from video paths at specified frames
or heuristics-based 'best frames'.
"""

import logging
from pathlib import Path
from typing import Any, Optional
import imageio
import numpy as np
from PIL import Image


class ThumbnailGenerator:
    """Extracts, processes, and saves thumbnail images from video files."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize ThumbnailGenerator.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.thumbnail_dir = self.workspace_dir / "core" / "export" / "thumbnails"
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(self.__class__.__name__)

    def generate_thumbnail(
        self,
        video_path: Path,
        output_thumbnail_path: Optional[Path] = None,
        position: str = "middle",
        frame_idx: Optional[int] = None
    ) -> Path:
        """Extract a single frame from the video, convert to PNG, and save.

        Args:
            video_path: Source video file path.
            output_thumbnail_path: Target PNG save path. If None, auto-generated in thumbnail_dir.
            position: Positioning strategy ("start", "middle", "end", "best").
            frame_idx: Exact frame index (overrides position).

        Returns:
            The Path to the generated thumbnail PNG.
        """
        video_path = Path(video_path).resolve()
        if not video_path.exists():
            raise FileNotFoundError(f"Source video not found: {video_path}")

        if output_thumbnail_path is None:
            output_thumbnail_path = self.thumbnail_dir / f"{video_path.stem}_thumb.png"
        else:
            output_thumbnail_path = Path(output_thumbnail_path).resolve()
            output_thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

        self._logger.info(f"Generating thumbnail for {video_path.name} (strategy={position}, frame={frame_idx})")

        reader = None
        try:
            reader = imageio.get_reader(str(video_path))
            meta = reader.get_meta_data()
            fps = meta.get("fps", 30)
            duration = meta.get("duration", 0.0)
            
            # Retrieve total number of frames safely
            try:
                total_frames = reader.count_frames()
            except Exception:
                if duration > 0:
                    total_frames = int(duration * fps)
                else:
                    total_frames = 100 # Default fallback

            # Determine frame index to read
            target_idx = 0
            if frame_idx is not None:
                target_idx = max(0, min(total_frames - 1, frame_idx))
            elif position == "start":
                target_idx = 0
            elif position == "middle":
                target_idx = total_frames // 2
            elif position == "end":
                target_idx = max(0, total_frames - 2)
            elif position == "best":
                target_idx = self._find_best_frame(reader, total_frames)
            else:
                target_idx = total_frames // 2

            # Read frame
            frame = reader.get_data(target_idx)
            
            # Save using PIL
            img = Image.fromarray(frame)
            img.save(output_thumbnail_path, "PNG")
            self._logger.info(f"Successfully saved thumbnail to {output_thumbnail_path.name}")
            return output_thumbnail_path

        except Exception as e:
            self._logger.error(f"Failed to generate thumbnail: {e}")
            raise
        finally:
            if reader is not None:
                try:
                    reader.close()
                except Exception:
                    pass

    def _find_best_frame(self, reader: Any, total_frames: int) -> int:
        """Finds the frame with the highest standard deviation / detail level to avoid black or blank frames.
        
        Args:
            reader: Imageio video reader.
            total_frames: Total count of frames.

        Returns:
            Best frame index.
        """
        # We sample up to 10 frames distributed across the video (avoiding the very beginning and very end)
        sample_indices = []
        if total_frames > 10:
            start_offset = total_frames // 10
            end_offset = total_frames - start_offset
            sample_indices = [int(x) for x in np.linspace(start_offset, end_offset - 1, 8)]
        else:
            sample_indices = list(range(total_frames))

        best_idx = total_frames // 2
        max_std = -1.0

        for idx in sample_indices:
            try:
                frame = reader.get_data(idx)
                # Compute average standard deviation across RGB channels
                std_dev = np.std(frame)
                if std_dev > max_std:
                    max_std = std_dev
                    best_idx = idx
            except Exception:
                continue

        return best_idx
