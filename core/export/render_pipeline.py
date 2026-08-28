"""RenderPipeline for compositing intro/outro clips, applying watermarks with transparency,
and burning styled subtitles on sequential frames.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple
import imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class RenderPipeline:
    """Handles visual frame composition including watermarks, subtitle burning, and intro/outro clips."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize RenderPipeline.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.render_cache_dir = self.workspace_dir / "core" / "export" / "render_cache"
        self.render_cache_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(self.__class__.__name__)

    def parse_srt(self, srt_content: str) -> List[Tuple[float, float, str]]:
        """Parse SRT subtitle format content into a list of (start_time, end_time, text) tuples.

        Args:
            srt_content: String SRT contents.

        Returns:
            List of parsed subtitles.
        """
        subtitles = []
        blocks = srt_content.strip().split("\n\n")
        
        def parse_time(t_str: str) -> float:
            # Format: 00:00:00,000 -> hh:mm:ss,ms
            parts = t_str.replace(",", ".").split(":")
            if len(parts) != 3:
                return 0.0
            h = int(parts[0])
            m = int(parts[1])
            s = float(parts[2])
            return h * 3600.0 + m * 60.0 + s

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                # Line 0: Index
                # Line 1: Timestamps
                # Line 2+: Text
                times = lines[1].split("-->")
                if len(times) == 2:
                    try:
                        start = parse_time(times[0].strip())
                        end = parse_time(times[1].strip())
                        text = "\n".join(lines[2:])
                        subtitles.append((start, end, text))
                    except Exception:
                        pass
        return subtitles

    def process_frames(
        self,
        video_reader: Any,
        width: int,
        height: int,
        fps: int,
        watermark_path: str = "",
        watermark_opacity: float = 0.5,
        burn_subtitles: bool = False,
        srt_content: str = "",
        intro_path: str = "",
        outro_path: str = ""
    ) -> Generator[np.ndarray, None, None]:
        """Yield frames sequentially, adding intro, watermark/subtitles, and outro.

        Args:
            video_reader: Imageio reader for the main video.
            width: Target frame width.
            height: Target frame height.
            fps: Output frame rate.
            watermark_path: Path to watermark overlay image.
            watermark_opacity: Alpha opacity of watermark.
            burn_subtitles: Draw subtitles on the main video frames.
            srt_content: SRT format subtitle content.
            intro_path: Path to intro video clip.
            outro_path: Path to outro video clip.

        Yields:
            Numpy array of RGB frame pixels.
        """
        # Load watermark if present
        watermark_img = None
        if watermark_path:
            try:
                wm_p = Path(watermark_path)
                if wm_p.exists():
                    # Load and convert to RGBA
                    raw_wm = Image.open(wm_p).convert("RGBA")
                    # Scale watermark to be ~15% of the video width
                    wm_w = int(width * 0.15)
                    aspect = raw_wm.height / raw_wm.width
                    wm_h = int(wm_w * aspect)
                    raw_wm = raw_wm.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
                    
                    # Apply opacity to alpha channel
                    alpha = raw_wm.split()[3]
                    alpha = alpha.point(lambda p: int(p * watermark_opacity))
                    raw_wm.putalpha(alpha)
                    watermark_img = raw_wm
                    self._logger.info(f"Loaded watermark overlay: {wm_p.name} ({wm_w}x{wm_h})")
            except Exception as e:
                self._logger.error(f"Failed to load watermark: {e}")

        # Parse subtitles if burning is enabled
        subtitles = []
        if burn_subtitles and srt_content:
            subtitles = self.parse_srt(srt_content)
            self._logger.info(f"Parsed {len(subtitles)} subtitle segments for burning.")

        # 1. Yield Intro Frames
        if intro_path:
            intro_p = Path(intro_path)
            if intro_p.exists():
                self._logger.info(f"Rendering intro clip: {intro_p.name}")
                intro_reader = None
                try:
                    intro_reader = imageio.get_reader(str(intro_p))
                    for frame in intro_reader:
                        # Resize to match target resolution
                        img = Image.fromarray(frame).resize((width, height), Image.Resampling.LANCZOS)
                        yield np.array(img)
                except Exception as e:
                    self._logger.error(f"Error processing intro clip: {e}")
                finally:
                    if intro_reader is not None:
                        try:
                            intro_reader.close()
                        except Exception:
                            pass

        # 2. Yield Main Video Frames (with watermark and subtitles applied)
        self._logger.info("Rendering main video segment frames...")
        frame_idx = 0
        for frame in video_reader:
            t = frame_idx / fps
            img = Image.fromarray(frame).resize((width, height), Image.Resampling.LANCZOS)

            # Apply watermark overlay
            if watermark_img is not None:
                # Place watermark in Top-Right corner with 20px padding
                pos_x = width - watermark_img.width - 20
                pos_y = 20
                
                # Composite
                wm_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                wm_canvas.paste(watermark_img, (pos_x, pos_y))
                img = Image.alpha_composite(img.convert("RGBA"), wm_canvas).convert("RGB")

            # Apply subtitles
            if burn_subtitles and subtitles:
                # Find active subtitle
                active_text = ""
                for start, end, text in subtitles:
                    if start <= t <= end:
                        active_text = text
                        break
                
                if active_text:
                    self._draw_subtitles_on_image(img, active_text, width, height)

            yield np.array(img)
            frame_idx += 1

        # 3. Yield Outro Frames
        if outro_path:
            outro_p = Path(outro_path)
            if outro_p.exists():
                self._logger.info(f"Rendering outro clip: {outro_p.name}")
                outro_reader = None
                try:
                    outro_reader = imageio.get_reader(str(outro_p))
                    for frame in outro_reader:
                        img = Image.fromarray(frame).resize((width, height), Image.Resampling.LANCZOS)
                        yield np.array(img)
                except Exception as e:
                    self._logger.error(f"Error processing outro clip: {e}")
                finally:
                    if outro_reader is not None:
                        try:
                            outro_reader.close()
                        except Exception:
                            pass

    def _draw_subtitles_on_image(self, img: Image.Image, text: str, w: int, h: int) -> None:
        """Render caption text overlays near the bottom center of the PIL Image."""
        draw = ImageDraw.Draw(img)
        font_size = max(12, int(h * 0.04))
        
        # Word wrap text
        char_w = font_size * 0.6
        max_chars = int(w * 0.8 / char_w)
        words = text.split()
        lines = []
        cur_line = []
        for word in words:
            if len(" ".join(cur_line + [word])) <= max_chars:
                cur_line.append(word)
            else:
                lines.append(" ".join(cur_line))
                cur_line = [word]
        if cur_line:
            lines.append(" ".join(cur_line))

        text_y = int(h * 0.82) - (len(lines) - 1) * font_size
        
        for line in lines:
            line_w = len(line) * char_w
            text_x = int((w - line_w) / 2)
            
            # Draw semi-transparent background box for legibility
            draw.rectangle(
                [text_x - 5, text_y - 2, text_x + line_w + 5, text_y + font_size + 2],
                fill=(0, 0, 0, 160)
            )
            # Draw yellow text
            draw.text((text_x, text_y), line, fill=(250, 204, 21))
            text_y += font_size + 4
