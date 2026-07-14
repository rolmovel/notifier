"""Appointment model representing a single row from the Excel file."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from src.services.phone_normalizer import normalize_phone

# E.164 format regex: + followed by 7-15 digits (first digit 1-9)
_E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")


class Appointment(BaseModel):
    """A single appointment row read from the Excel file."""

    row_number: int = Field(ge=1)
    start_time: datetime
    duration_minutes: int = Field(ge=1)
    gabinete: str = ""
    patient_name: str
    appointment_type: str
    phone_landline: Optional[str] = None
    phone_mobile: Optional[str] = None
    # The country code used for normalization (injected by reader)
    country_code: str = "+34"

    @computed_field  # type: ignore[misc]
    @property
    def phone_normalized(self) -> Optional[str]:
        """E.164-normalized phone (mobile preferred, fallback to landline)."""
        # Try mobile first
        if self.phone_mobile:
            normalized = normalize_phone(self.phone_mobile, self.country_code)
            if normalized:
                return normalized
        # Fallback to landline
        if self.phone_landline:
            normalized = normalize_phone(self.phone_landline, self.country_code)
            if normalized:
                return normalized
        return None

    @computed_field  # type: ignore[misc]
    @property
    def is_valid(self) -> bool:
        """Whether the row passed validation."""
        return len(self.validation_errors) == 0

    @computed_field  # type: ignore[misc]
    @property
    def validation_errors(self) -> list[str]:
        """List of validation error messages (empty if valid)."""
        errors: list[str] = []

        if not self.patient_name or not self.patient_name.strip():
            errors.append("El nombre del paciente es obligatorio")

        if not self.appointment_type or not self.appointment_type.strip():
            errors.append("El tipo de cita es obligatorio")

        if not self.phone_mobile and not self.phone_landline:
            errors.append("Debe haber al menos un teléfono (fijo o móvil)")
        else:
            phone = self.phone_normalized
            if phone is None:
                errors.append("No se pudo normalizar ningún teléfono válido")
            elif not _E164_PATTERN.match(phone):
                errors.append(f"El teléfono normalizado no es válido: {phone}")

        if self.duration_minutes <= 0:
            errors.append("La duración debe ser un entero positivo")

        return errors

    def model_dump_json_safe(self) -> dict:
        """Return a JSON-serializable dict without computed fields causing recursion."""
        data = self.model_dump(mode="json")
        return data
