"""Settings model for the WhatsApp Desktop Utility."""

from __future__ import annotations

from pydantic import BaseModel, Field


DEFAULT_MESSAGE_TEMPLATE = """Hola {{Paciente}},

Le recordamos su cita el {{Fecha y hora}} para {{Tipo de cita}}.

Por favor, responda 'CONFIRMAR' para ratificar su asistencia o póngase en contacto si necesita reprogramar.

¡Gracias!"""


class Settings(BaseModel):
    """User-configurable application settings, persisted as JSON."""

    bridge_port: int = Field(default=3001, ge=1, le=65535)
    default_country_code: str = Field(default="+34")
    message_template: str = Field(default=DEFAULT_MESSAGE_TEMPLATE)
    last_file_path: str | None = Field(default=None)
    # Name of the Excel header (as it appears in the file) that holds the
    # destination phone number. Configured by the user in Settings.
    phone_header: str = Field(default="")
    send_interval_ms: int = Field(default=1500, ge=0, le=300000)
    delivery_timeout_s: float = Field(default=45.0, gt=0, le=3600)
    poll_interval_s: float = Field(default=2.0, gt=0, le=300)
    max_retries: int = Field(default=3, ge=0, le=20)
    retry_backoff_base_s: float = Field(default=5.0, ge=0, le=3600)
    circuit_threshold: int = Field(default=3, ge=1, le=100)
    circuit_cooldown_s: float = Field(default=60.0, gt=0, le=3600)


