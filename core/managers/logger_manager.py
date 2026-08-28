"""Logging Manager for AI News Studio.

Sets up application-wide file and console logging with rotating logs,
and exposes a custom handler for UI integration.
"""

from collections import deque
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, List


class UIQueueHandler(logging.Handler):
    """Custom logging handler that buffers log messages and triggers callbacks for UI updates."""

    def __init__(self, max_buffer: int = 500) -> None:
        """Initialize UI handler.

        Args:
            max_buffer: Maximum number of log messages to hold in memory.
        """
        super().__init__()
        self.buffer: deque = deque(maxlen=max_buffer)
        self.callbacks: List[Callable[[str], None]] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Process a log record and append it to the buffer.

        Args:
            record: The log record.
        """
        try:
            msg = self.format(record)
            self.buffer.append(msg)
            for callback in self.callbacks:
                try:
                    callback(msg)
                except Exception:
                    pass  # Avoid crash in logger if a callback fails
        except Exception:
            self.handleError(record)

    def register_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback that receives every new formatted log message.

        Args:
            callback: Function receiving a string log line.
        """
        self.callbacks.append(callback)
        # Flush existing buffer to the new callback
        for msg in self.buffer:
            try:
                callback(msg)
            except Exception:
                pass

    def unregister_callback(self, callback: Callable[[str], None]) -> None:
        """Unregister a callback.

        Args:
            callback: Function to remove.
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)


class LoggerManager:
    """Configures application-wide logging behavior."""

    def __init__(self, workspace_dir: Path, log_level: int = logging.INFO) -> None:
        """Initialize LoggerManager and configure logging handlers.

        Args:
            workspace_dir: Workspace root directory.
            log_level: Default logging level.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.log_dir = self.workspace_dir / "logs"
        self.log_file = self.log_dir / "app.log"
        self.log_level = log_level

        # Ensure directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create root logger
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(self.log_level)

        # Clear existing handlers
        self.root_logger.handlers = []

        # Common Formatter
        self.formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Console Handler
        self.console_handler = logging.StreamHandler()
        self.console_handler.setFormatter(self.formatter)
        self.console_handler.setLevel(self.log_level)
        self.root_logger.addHandler(self.console_handler)

        # Rotating File Handler (10MB size cap, keeps 5 logs backup)
        try:
            self.file_handler = RotatingFileHandler(
                self.log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8"
            )
            self.file_handler.setFormatter(self.formatter)
            self.file_handler.setLevel(self.log_level)
            self.root_logger.addHandler(self.file_handler)
        except Exception as e:
            logging.error(f"Failed to initialize rotating file handler: {e}")

        # UI Queue Handler
        self.ui_handler = UIQueueHandler()
        self.ui_handler.setFormatter(self.formatter)
        self.ui_handler.setLevel(self.log_level)
        self.root_logger.addHandler(self.ui_handler)

        logging.info("Logging successfully initialized. Output dir: %s", self.log_dir)

    def get_ui_handler(self) -> UIQueueHandler:
        """Get the active UIQueueHandler for widgets to subscribe to.

        Returns:
            The active UIQueueHandler instance.
        """
        return self.ui_handler
