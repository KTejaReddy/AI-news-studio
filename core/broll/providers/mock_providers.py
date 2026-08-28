"""Mock providers implementing BrollProvider for testing and offline fallback.
Generates actual playable MP4 videos and PNG images with animated indicators.
"""

from pathlib import Path
import numpy as np
import imageio
from PIL import Image, ImageDraw

from core.broll.providers.base_provider import BrollProvider


class BaseMockProvider(BrollProvider):
    """Base mock class helper to output physical playable media files."""

    def __init__(self, name: str) -> None:
        self.name = name

    def get_name(self) -> str:
        return self.name

    def generate(
        self,
        prompt: str,
        duration: float,
        aspect_ratio: str,
        fps: int,
        output_path: Path
    ) -> Path:
        """Create physical mockup visual media based on prompt/type requirements."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # We will determine if the file should be an image or a video based on suffix or duration.
        # But we'll support both. Let's inspect the suffix.
        is_video = output_path.suffix.lower() in [".mp4", ".avi", ".mov", ".webm", ".mkv"]

        # Default resolutions
        width, height = 640, 360
        if aspect_ratio == "9:16":
            width, height = 360, 640
        elif aspect_ratio == "1:1":
            width, height = 480, 480

        # Select color scheme based on provider name hash
        import hashlib
        color_hash = hashlib.md5(self.name.encode()).digest()
        bg_color = (int(color_hash[0] % 40) + 10, int(color_hash[1] % 40) + 15, int(color_hash[2] % 40) + 20)
        fg_color = (int(color_hash[3] % 150) + 100, int(color_hash[4] % 150) + 100, int(color_hash[5] % 150) + 100)

        if is_video:
            # Generate moving frames using imageio
            num_frames = int(duration * fps)
            if num_frames <= 0:
                num_frames = 1

            writer = imageio.get_writer(str(output_path), fps=fps)
            for f in range(num_frames):
                img = Image.new("RGB", (width, height), color=bg_color)
                d = ImageDraw.Draw(img)

                # Draw outer frame
                d.rectangle([(10, 10), (width - 10, height - 10)], outline=fg_color, width=2)

                # Draw a moving indicator
                phase = f / num_frames
                circle_x = int(50 + (width - 100) * phase)
                circle_y = int(height / 2 + np.sin(phase * np.pi * 4) * 30)
                d.ellipse([circle_x - 20, circle_y - 20, circle_x + 20, circle_y + 20], fill=fg_color)

                # Info text
                d.text((30, 30), f"Provider: {self.name}", fill=(255, 255, 255))
                d.text((30, 50), f"Prompt: {prompt[:40]}...", fill=(200, 200, 200))
                d.text((30, 70), f"Format: {aspect_ratio} | {fps} fps", fill=(170, 170, 170))
                d.text((30, 90), f"Duration: {duration}s | Frame {f+1}/{num_frames}", fill=(150, 150, 150))

                frame_np = np.array(img)
                writer.append_data(frame_np)

            writer.close()
        else:
            # Generate static image
            img = Image.new("RGB", (width, height), color=bg_color)
            d = ImageDraw.Draw(img)

            # Draw framing borders
            d.rectangle([(15, 15), (width - 15, height - 15)], outline=fg_color, width=3)
            
            # Simple artistic shapes (like a landscape or mock visual)
            d.polygon([(100, height - 50), (width // 2, 100), (width - 100, height - 50)], fill=fg_color)
            
            # Text overlays
            d.text((30, 30), f"Provider: {self.name} (Image Preset)", fill=(255, 255, 255))
            d.text((30, 50), f"Prompt: {prompt[:60]}", fill=(220, 220, 220))
            d.text((30, 75), f"Aspect Ratio: {aspect_ratio}", fill=(180, 180, 180))

            img.save(output_path, "PNG")

        return output_path


# Concrete implementation classes for each provider

class GeminiFlowProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Gemini Flow")


class VeoProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Veo")


class RunwayProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Runway")


class PikaProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Pika")


class LumaProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Luma")


class KlingProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Kling")


class HailuoProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Hailuo")


class ComfyUIProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Local ComfyUI")


class StableDiffusionProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Stable Diffusion")


class FluxProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Flux")


class FuProvider(BaseMockProvider):
    def __init__(self) -> None:
        super().__init__("Fu")
