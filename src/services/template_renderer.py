"""Template renderer — replace {{variables}} in the message template with data.

Placeholders use the original Excel header names as they appear in the file
(e.g. ``{{Paciente}}``, ``{{Fecha y hora}}``). They are resolved against the
appointment's ``raw_data`` mapping (header -> cell value), matched
case-insensitively and ignoring leading/trailing whitespace.

The renderer is fully decoupled from the Excel schema: it does not assume any
fixed set of columns.
"""

from __future__ import annotations

import re
import logging

from src.models.appointment import Appointment

logger = logging.getLogger(__name__)

# Match {{ ... }} allowing spaces, accents and punctuation in the name.
# Non-greedy so multiple placeholders on one line work correctly.
_TEMPLATE_VAR_PATTERN = re.compile(r"\{\{\s*(.+?)\s*\}\}")


def render_template(template: str, appointment: Appointment) -> str:
    """Render a message template by replacing {{variables}} with data.

    Variables are resolved against the Excel headers stored in
    ``appointment.raw_data`` (matched case-insensitively, ignoring leading/
    trailing whitespace).

    Args:
        template: The template string with {{variable}} placeholders.
        appointment: The appointment to extract data from.

    Returns:
        The rendered message string. Unknown variables are replaced with an
        empty string (and a warning is logged).
    """
    raw = appointment.raw_data or {}
    # Case-insensitive lookup index for raw headers
    raw_lookup: dict[str, str] = {
        key.strip().lower(): value for key, value in raw.items() if key
    }

    def replace_match(match: re.Match) -> str:
        var_name = match.group(1).strip()
        key = var_name.lower()
        if key in raw_lookup:
            return raw_lookup[key]
        # Unknown variable — leave blank with a warning
        logger.warning("Unknown template variable: {{%s}}", var_name)
        return ""

    return _TEMPLATE_VAR_PATTERN.sub(replace_match, template)


def get_available_variables(headers: list[str] | None = None) -> list[str]:
    """Return the list of available template variable names.

    When ``headers`` is provided (the Excel file's header row), the original
    header names are returned so the UI can show them as available
    placeholders. Otherwise an empty list is returned (no canonical fallback).
    """
    if headers:
        return [h for h in headers if h and h.strip()]
    return []
