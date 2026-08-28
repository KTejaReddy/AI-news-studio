"""TimelinePlayback for managing playhead timings, frames stepping, and loop settings.
"""

import logging
import time
from typing import Optional


class TimelinePlayback:
    """Manages playback state loops and frame calculations for preview renderers."""

    def __init__(self, fps: int = 30) -> None:
        """Initialize TimelinePlayback.

        Args:
            fps: Frame rate (frames per second).
        """
        self.fps = max(1, fps)
        self.frame_duration = 1.0 / self.fps
        self.current_time = 0.0
        self.playing = False
        self.loop = False
        self.last_tick: Optional[float] = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def play(self) -> None:
        """Resume playback, initializing tick clocks."""
        if not self.playing:
            self.playing = True
            self.last_tick = time.perf_counter()
            self._logger.debug("Playback started.")

    def pause(self) -> None:
        """Halt playback."""
        if self.playing:
            self.playing = False
            self.last_tick = None
            self._logger.debug("Playback paused.")

    def stop(self) -> None:
        """Reset playhead back to zero and stop."""
        self.playing = False
        self.current_time = 0.0
        self.last_tick = None
        self._logger.debug("Playback stopped. Playhead reset to 0.0s.")

    def set_time(self, seconds: float, total_duration: float) -> None:
        """Set playhead explicitly.

        Args:
            seconds: Target time in seconds.
            total_duration: Overall timeline duration limit.
        """
        self.current_time = max(0.0, min(seconds, total_duration))

    def next_frame(self, total_duration: float) -> None:
        """Step playhead forward by one frame.

        Args:
            total_duration: Overall timeline duration limit.
        """
        target_time = self.current_time + self.frame_duration
        if target_time > total_duration:
            if self.loop:
                self.current_time = 0.0
            else:
                self.current_time = total_duration
                self.pause()
        else:
            self.current_time = target_time

    def prev_frame(self) -> None:
        """Step playhead backward by one frame."""
        self.current_time = max(0.0, self.current_time - self.frame_duration)

    def update_tick(self, total_duration: float) -> float:
        """Tick clock calculation based on real-world elapsed time.

        Args:
            total_duration: Overall timeline duration limit.

        Returns:
            The new playhead current_time value.
        """
        if not self.playing:
            return self.current_time

        now = time.perf_counter()
        if self.last_tick is None:
            self.last_tick = now
            return self.current_time

        dt = now - self.last_tick
        self.last_tick = now

        target_time = self.current_time + dt
        if target_time >= total_duration:
            if self.loop:
                # Wrap around
                self.current_time = target_time % total_duration if total_duration > 0 else 0.0
            else:
                self.current_time = total_duration
                self.pause()
        else:
            self.current_time = target_time

        return self.current_time

    def get_current_frame(self) -> int:
        """Compute frame index number corresponding to the current time.

        Returns:
            Frame index integer.
        """
        return int(self.current_time * self.fps)
