"""History store — save/load send sessions as JSON files in platformdirs."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from platformdirs import user_data_dir

from src.models.send_history import SendSession
from src.models.send_result import SendResult, SendStatus

logger = logging.getLogger(__name__)

APP_NAME = "whatsapp-notifier"
HISTORY_DIRNAME = "history"


def get_history_dir() -> Path:
    """Return the path to the history directory."""
    data_dir = Path(user_data_dir(APP_NAME)) / HISTORY_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


class HistoryStore:
    """Manages persistence of send sessions as JSON files."""

    def __init__(self, history_dir: Path | None = None) -> None:
        self._history_dir = history_dir or get_history_dir()

    @property
    def history_dir(self) -> Path:
        return self._history_dir

    def save_session(self, session: SendSession) -> Path:
        """Save a send session to a JSON file.

        Args:
            session: The SendSession to save.

        Returns:
            Path to the saved file.
        """
        # Use the session's started_at timestamp for the filename
        timestamp = session.started_at.strftime("%Y%m%dT%H%M%S")
        filename = f"{timestamp}_{session.session_id[:8]}.json"
        file_path = self._history_dir / filename

        try:
            data = session.model_dump(mode="json")
            file_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            logger.info("Session saved to %s", file_path)
            return file_path
        except OSError as exc:
            logger.error("Failed to save session: %s", exc)
            raise

    def list_sessions(self) -> list[dict]:
        """List all past sessions sorted by date (newest first).

        Returns:
            List of dicts with: session_id, started_at, completed_at,
            source_file, total_appointments, sent_count, failed_count.
        """
        sessions: list[dict] = []

        for file_path in self._history_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                session = SendSession(**data)
                sessions.append({
                    "session_id": session.session_id,
                    "started_at": session.started_at,
                    "completed_at": session.completed_at,
                    "source_file": session.source_file,
                    "total_appointments": session.total_appointments,
                    "valid_appointments": session.valid_appointments,
                    "sent_count": session.sent_count,
                    "failed_count": session.failed_count,
                    "file_path": str(file_path),
                })
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.warning("Failed to load session %s: %s", file_path, exc)

        # Sort by started_at descending (newest first)
        sessions.sort(key=lambda s: s["started_at"], reverse=True)
        return sessions

    def load_session(self, file_path: str | Path) -> SendSession | None:
        """Load a specific session by file path.

        Args:
            file_path: Path to the session JSON file.

        Returns:
            SendSession object or None if loading fails.
        """
        path = Path(file_path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SendSession(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.error("Failed to load session %s: %s", path, exc)
            return None

    def delete_session(self, file_path: str | Path) -> bool:
        """Delete a session file.

        Args:
            file_path: Path to the session JSON file.

        Returns:
            True if deleted, False if file not found or error.
        """
        path = Path(file_path)
        try:
            path.unlink()
            logger.info("Deleted session: %s", path)
            return True
        except FileNotFoundError:
            logger.warning("Session file not found: %s", path)
            return False
        except OSError as exc:
            logger.error("Failed to delete session %s: %s", path, exc)
            return False
