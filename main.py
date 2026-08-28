"""Main bootstrap entry point for the AI News Studio desktop application.

Handles configuration parsing, logging setup, dependency injection, and global
exception interception.
"""

from datetime import datetime
import logging
from pathlib import Path
import sys
import traceback

import customtkinter as ctk

from app.gui import MainWindow
from core.managers import (
    AssetManager,
    ConfigManager,
    HistoryManager,
    LoggerManager,
    ModelManager,
    OutputManager,
    ProjectManager,
    SettingsManager,
)

# Active window reference for global exception handling dialogs
_app_window_ref: MainWindow = None


def global_exception_hook(exc_type, exc_value, exc_traceback) -> None:
    """Intercept unhandled system execution crashes and log detailed tracebacks to disk.

    Args:
        exc_type: Class type of the exception.
        exc_value: The exception instance.
        exc_traceback: Traceback traceback object.
    """
    # Print to stderr for standard console debugging
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

    # Format traceback details
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_text = "".join(tb_lines)

    # Resolve log path
    workspace_dir = Path(__file__).parent.resolve()
    crash_dir = workspace_dir / "logs"
    crash_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    crash_file = crash_dir / f"crash_{timestamp}.log"

    # Write log file
    try:
        with open(crash_file, "w", encoding="utf-8") as f:
            f.write(f"AI News Studio Crash Report - {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n")
            f.write(tb_text)
        logging.error(f"Critical execution error intercepted. Traceback logged to {crash_file}")
    except Exception as e:
        print(f"Failed to write crash log: {e}", file=sys.stderr)

    # Display error dialog if GUI window has booted
    global _app_window_ref
    if _app_window_ref is not None:
        try:
            # Tkinter thread safe scheduling
            _app_window_ref.after(
                0,
                lambda: _app_window_ref.show_error(
                    "Unexpected Application Crash",
                    f"An unhandled exception occurred.\n\nError details logged to:\n{crash_file.name}\n\n{exc_value}"
                )
            )
        except Exception as e:
            print(f"Failed to display crash window popup: {e}", file=sys.stderr)


def tkinter_callback_exception_hook(self, exc_type, exc_value, exc_traceback) -> None:
    """Interception hook for exceptions arising inside tkinter event loops.

    Note: The first argument ``self`` is the Tkinter widget instance that
    Tkinter passes when invoking ``report_callback_exception`` as a bound
    method on the CTk class.  It must be accepted but is not used here.
    """
    global_exception_hook(exc_type, exc_value, exc_traceback)


def main() -> None:
    """Bootstrap application settings, inject dependencies and launch main GUI loop."""
    # 1. Resolve workspace root path
    workspace_dir = Path(__file__).parent.resolve()

    # 2. Boot up core LoggerManager
    log_mgr = LoggerManager(workspace_dir=workspace_dir, log_level=logging.DEBUG)
    logger = logging.getLogger("Bootstrap")
    logger.info("Starting bootstrap phase...")

    # 3. Setup global crash catches
    sys.excepthook = global_exception_hook
    ctk.CTk.report_callback_exception = tkinter_callback_exception_hook
    logger.info("Global crash interception hooks successfully registered.")

    # 4. Instantiate Core Business Managers (Dependency Injection)
    config_mgr = ConfigManager(workspace_dir=workspace_dir)
    settings_mgr = SettingsManager(config_manager=config_mgr)
    project_mgr = ProjectManager(workspace_dir=workspace_dir, config_manager=config_mgr)
    asset_mgr = AssetManager(workspace_dir=workspace_dir)
    model_mgr = ModelManager(workspace_dir=workspace_dir, config_manager=config_mgr)
    output_mgr = OutputManager(workspace_dir=workspace_dir, config_manager=config_mgr)
    history_mgr = HistoryManager(workspace_dir=workspace_dir)
    
    logger.info("Application manager layers resolved successfully.")

    # 5. Initialize & configure CustomTkinter App Window
    logger.info("Initializing CustomTkinter MainWindow...")
    app = MainWindow(
        config_mgr=config_mgr,
        settings_mgr=settings_mgr,
        project_mgr=project_mgr,
        asset_mgr=asset_mgr,
        model_mgr=model_mgr,
        output_mgr=output_mgr,
        history_mgr=history_mgr,
    )

    # Bind active reference for global error callbacks
    global _app_window_ref
    _app_window_ref = app

    # 6. Execute Application Main Loop
    logger.info("Launching GUI main event loop...")
    try:
        app.mainloop()
    finally:
        logger.info("Application lifecycle terminated.")


if __name__ == "__main__":
    main()
