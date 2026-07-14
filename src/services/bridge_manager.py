"""Bridge manager — start/stop the Node.js Baileys bridge subprocess."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


def _get_bridge_dir() -> Path:
    """Resolve the bridge directory, handling both dev and PyInstaller modes."""
    if getattr(sys, "frozen", False):
        # PyInstaller: bridge/ is bundled next to the executable
        return Path(sys.executable).parent / "bridge"
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller onedir: _MEIPASS points to the bundle root
        return Path(sys._MEIPASS) / "bridge"
    # Development mode
    return Path(__file__).parent.parent.parent / "bridge"


# Path to the bridge script
BRIDGE_SCRIPT = _get_bridge_dir() / "whatsapp-bridge.js"

# Maximum time to wait for bridge to become responsive (seconds)
_BRIDGE_STARTUP_TIMEOUT = 10

# Polling interval for health check (seconds)
_POLL_INTERVAL = 0.5


class BridgeManager:
    """Manages the lifecycle of the Node.js Baileys bridge subprocess."""

    def __init__(self, port: int = 3001) -> None:
        self._port = port
        self._process: subprocess.Popen | None = None
        self._base_url = f"http://127.0.0.1:{port}"

    @property
    def port(self) -> int:
        return self._port

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def is_running(self) -> bool:
        """Check if the bridge subprocess is running."""
        return self._process is not None and self._process.poll() is None

    async def is_bridge_responsive(self) -> bool:
        """Check if the bridge is already running and responsive."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self._base_url}/status")
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def start(self) -> bool:
        """Start the bridge subprocess if not already running.

        Returns:
            True if the bridge is running and responsive, False on failure.
        """
        # Check if bridge is already running
        if await self.is_bridge_responsive():
            logger.info("Bridge already running on port %d", self._port)
            return True

        if self.is_running:
            logger.info("Bridge process running but not responsive, waiting...")
        else:
            # Start the subprocess
            if not BRIDGE_SCRIPT.exists():
                logger.error("Bridge script not found: %s", BRIDGE_SCRIPT)
                return False

            node_modules = BRIDGE_SCRIPT.parent / "node_modules"
            if not node_modules.exists():
                logger.error("Node modules not installed. Run 'npm install' in bridge/")
                return False

            try:
                self._process = subprocess.Popen(
                    ["node", str(BRIDGE_SCRIPT), "--port", str(self._port)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(BRIDGE_SCRIPT.parent),
                    # Create a new process group so we can kill the whole tree
                    start_new_session=True,
                )
                logger.info("Bridge subprocess started (PID: %d)", self._process.pid)
            except FileNotFoundError:
                logger.error("Node.js not found. Please install Node.js 18+.")
                return False
            except Exception as exc:
                logger.error("Failed to start bridge: %s", exc)
                return False

        # Wait for the bridge to become responsive
        elapsed = 0.0
        while elapsed < _BRIDGE_STARTUP_TIMEOUT:
            if self._process and self._process.poll() is not None:
                # Process exited
                stderr_output = ""
                if self._process.stderr:
                    stderr_output = self._process.stderr.read().decode("utf-8", errors="replace")
                logger.error("Bridge process exited early. stderr: %s", stderr_output)
                return False

            if await self.is_bridge_responsive():
                logger.info("Bridge is responsive on port %d", self._port)
                return True

            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

        logger.error("Bridge did not become responsive within %d seconds", _BRIDGE_STARTUP_TIMEOUT)
        self.stop()
        return False

    def stop(self) -> None:
        """Stop the bridge subprocess."""
        if self._process is None:
            return

        if self._process.poll() is None:
            logger.info("Stopping bridge subprocess (PID: %d)", self._process.pid)
            try:
                # Try graceful shutdown first (SIGTERM)
                if sys.platform == "win32":
                    self._process.terminate()
                else:
                    os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)

                # Wait up to 5 seconds for graceful shutdown
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Bridge did not stop gracefully, force killing")
                    if sys.platform == "win32":
                        self._process.kill()
                    else:
                        os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                    self._process.wait(timeout=2)
            except ProcessLookupError:
                pass
            except Exception as exc:
                logger.error("Error stopping bridge: %s", exc)

        self._process = None
        logger.info("Bridge stopped")
