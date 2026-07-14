"""Entry point for the WhatsApp Notifier desktop application."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `src` is importable
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PySide6.QtWidgets import QApplication

from src.services.bridge_manager import BridgeManager
from src.services.settings_store import SettingsStore
from src.ui.main_window import MainWindow


def setup_logging() -> None:
    """Configure logging for the application."""
    log_dir = Path.home() / ".whatsapp-notifier" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "notifier.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> int:
    """Run the WhatsApp Notifier desktop application."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting WhatsApp Notifier...")

    app = QApplication(sys.argv)
    app.setApplicationName("WhatsApp Notifier")
    app.setOrganizationName("WhatsAppNotifier")

    # Load settings
    settings_store = SettingsStore()
    settings = settings_store.load()

    bridge_url = f"http://127.0.0.1:{settings.bridge_port}"
    bridge_manager = BridgeManager(port=settings.bridge_port)

    # Start the bridge (async — must use event loop)
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        success = loop.run_until_complete(bridge_manager.start())
        if success:
            logger.info("WhatsApp bridge started successfully")
        else:
            logger.warning("Bridge failed to start — continuing without it")
    except Exception as exc:
        logger.warning("Bridge startup error: %s", exc)
    finally:
        loop.close()

    # Create main window
    window = MainWindow(
        settings=settings,
        bridge_url=bridge_url,
        settings_store=settings_store,
    )
    window.show()

    exit_code = app.exec()

    # Cleanup
    try:
        bridge_manager.stop()
        logger.info("WhatsApp bridge stopped")
    except Exception as exc:
        logger.warning("Error stopping bridge: %s", exc)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
