"""Settings model for the WhatsApp Desktop Utility."""

from __future__ import annotations

from pydantic import BaseModel, Field


DEFAULT_MESSAGE_TEMPLATE = """Hola {{patient_name}},

Le recordamos su cita el {{appointment_date}} a las {{appointment_time}} para {{appointment_type}}.

Por favor, responda 'CONFIRMAR' para ratificar su asistencia o póngase en contacto si necesita reprogramar.

¡Gracias!"""


class Settings(BaseModel):
    """User-configurable application settings, persisted as JSON."""

    bridge_port: int = Field(default=3001, ge=1, le=65535)
    default_country_code: str = Field(default="+34")
    message_template: str = Field(default=DEFAULT_MESSAGE_TEMPLATE)
    last_file_path: str | None = Field(default=None)
