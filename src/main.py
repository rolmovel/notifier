"""Application entry point for the WhatsApp Desktop Utility."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.models.settings import Settings
from src.services.bridge_manager import BridgeManager
from src.services.settings_store import SettingsStore
from src.ui.main_window import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Initialize and run the application."""
    # Load settings
    settings_store = SettingsStore()
    settings = settings_store.load()
    logger.info(
        "Settings loaded: port=%d, country=%s",
        settings.bridge_port,
        settings.default_country_code,
    )

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("WhatsApp Notifier")
    app.setApplicationDisplayName("WhatsApp Notifier")

    # Start bridge manager
    bridge_url = f"http://127.0.0.1:{settings.bridge_port}"
    bridge_manager = BridgeManager(port=settings.bridge_port)

    # Create main window
    window = MainWindow(settings, bridge_url=bridge_url, settings_store=settings_store)
    window.show()

    # Start bridge in the background (non-blocking — don't fail if bridge isn't ready)
    import asyncio

    async def start_bridge():
        success = await bridge_manager.start()
        if not success:
            logger.warning("Bridge not started — WhatsApp features will not work until started")
            window.statusBar().showMessage(
                "⚠ Bridge no iniciado. Instala dependencias con: cd bridge && npm install",
                10000,
            )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(start_bridge())
    finally:
        loop.close()

    # Run the application
    exit_code = app.exec()

    # Clean shutdown — stop the bridge
    logger.info("Stopping bridge...")
    bridge_manager.stop()

    # Save settings on exit
    settings_store.save(settings)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
