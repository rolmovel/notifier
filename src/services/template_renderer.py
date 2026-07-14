"""Template renderer — replace {{variables}} in the message template with appointment data."""

from __future__ import annotations

import re
import logging

from src.models.appointment import Appointment

logger = logging.getLogger(__name__)

# All available template variables
AVAILABLE_VARIABLES = [
    "patient_name",
    "appointment_date",
    "appointment_time",
    "appointment_type",
    "gabinete",
]

# Pattern to match {{variable_name}} (with optional whitespace)
_TEMPLATE_VAR_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_template(template: str, appointment: Appointment) -> str:
    """Render a message template by replacing {{variables}} with appointment data.

    Args:
        template: The template string with {{variable}} placeholders.
        appointment: The appointment to extract data from.

    Returns:
        The rendered message string.
    """
    variable_values = {
        "patient_name": appointment.patient_name,
        "appointment_date": appointment.start_time.strftime("%Y-%m-%d"),
        "appointment_time": appointment.start_time.strftime("%H:%M"),
        "appointment_type": appointment.appointment_type,
        "gabinete": appointment.gabinete or "",
    }

    def replace_match(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in variable_values:
            return variable_values[var_name]
        # Unknown variable — leave blank with a warning
        logger.warning("Unknown template variable: {{%s}}", var_name)
        return ""

    return _TEMPLATE_VAR_PATTERN.sub(replace_match, template)


def get_available_variables() -> list[str]:
    """Return the list of available template variable names."""
    return AVAILABLE_VARIABLES.copy()
