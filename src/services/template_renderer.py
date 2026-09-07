"""Template renderer — replace {{variables}} in the message template with data.

Placeholders use the original Excel header names as they appear in the file
(e.g. ``{{Paciente}}``, ``{{Fecha y hora}}``). They are resolved against the
appointment's ``raw_data`` mapping (header -> cell value).

For backward compatibility, a small set of canonical aliases is also supported
(``patient_name``, ``appointment_date``, ``appointment_time``,
``appointment_type``, ``gabinete``) derived from the parsed Appointment fields.
"""

from __future__ import annotations

import re
import logging

from src.models.appointment import Appointment

logger = logging.getLogger(__name__)

# Canonical aliases (backward compatibility with older templates).
CANONICAL_VARIABLES = [
    "patient_name",
    "appointment_date",
    "appointment_time",
    "appointment_type",
    "gabinete",
]

# Match {{ ... }} allowing spaces, accents and punctuation in the name.
# Non-greedy so multiple placeholders on one line work correctly.
_TEMPLATE_VAR_PATTERN = re.compile(r"\{\{\s*(.+?)\s*\}\}")


def _canonical_values(appointment: Appointment) -> dict[str, str]:
    """Return canonical alias -> value mapping derived from parsed fields."""
    return {
        "patient_name": appointment.patient_name,
        "appointment_date": appointment.start_time.strftime("%Y-%m-%d"),
        "appointment_time": appointment.start_time.strftime("%H:%M"),
        "appointment_type": appointment.appointment_type,
        "gabinete": appointment.gabinete or "",
    }


def render_template(template: str, appointment: Appointment) -> str:
    """Render a message template by replacing {{variables}} with data.

    Variables are resolved first against the Excel headers stored in
    ``appointment.raw_data`` (matched case-insensitively, ignoring leading/
    trailing whitespace), then against the canonical aliases.

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
    canonical = _canonical_values(appointment)

    def replace_match(match: re.Match) -> str:
        var_name = match.group(1).strip()
        key = var_name.lower()
        if key in raw_lookup:
            return raw_lookup[key]
        if key in canonical:
            return canonical[key]
        # Unknown variable — leave blank with a warning
        logger.warning("Unknown template variable: {{%s}}", var_name)
        return ""

    return _TEMPLATE_VAR_PATTERN.sub(replace_match, template)


def get_available_variables(headers: list[str] | None = None) -> list[str]:
    """Return the list of available template variable names.

    When ``headers`` is provided (the Excel file's header row), the original
    header names are returned so the UI can show them as available
    placeholders. Otherwise the canonical aliases are returned as a fallback.
    """
    if headers:
        return [h for h in headers if h and h.strip()]
    return CANONICAL_VARIABLES.copy()
