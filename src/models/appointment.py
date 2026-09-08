"""Appointment model representing a single row from the Excel file.

The model is intentionally schema-agnostic: it stores the row as a mapping of
original Excel header -> cell value (``raw_data``) plus the name of the header
that the user has mapped as the destination phone (``phone_header``). No other
fields are fixed, so any Excel schema is accepted.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from src.services.phone_normalizer import normalize_phone

# E.164 format regex: + followed by 7-15 digits (first digit 1-9)
_E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")


class Appointment(BaseModel):
    """A single appointment row read from the Excel file.

    The row is stored verbatim in ``raw_data`` (header -> string cell value).
    The phone used for sending is taken from ``raw_data[phone_header]`` and
    normalized using ``country_code``.
    """

    row_number: int = Field(ge=1)
    # Original Excel header -> string cell value for the row.
    raw_data: dict[str, str] = Field(default_factory=dict)
    # Name of the header (as it appears in the Excel) that holds the phone.
    phone_header: str = ""
    # Country code used for phone normalization (injected by reader).
    country_code: str = "+34"

    @computed_field  # type: ignore[misc]
    @property
    def phone_raw(self) -> Optional[str]:
        """The raw phone value read from the mapped phone header, if any."""
        if not self.phone_header:
            return None
        # Case-insensitive lookup against raw_data keys.
        target = self.phone_header.strip().lower()
        for key, value in self.raw_data.items():
            if key.strip().lower() == target:
                return value
        return None

    @computed_field  # type: ignore[misc]
    @property
    def phone_normalized(self) -> Optional[str]:
        """E.164-normalized phone, or None if it cannot be normalized."""
        raw = self.phone_raw
        if not raw:
            return None
        return normalize_phone(raw, self.country_code)

    @computed_field  # type: ignore[misc]
    @property
    def is_valid(self) -> bool:
        """Whether the row has a normalizable phone to send to."""
        phone = self.phone_normalized
        return phone is not None and bool(_E164_PATTERN.match(phone))

    @computed_field  # type: ignore[misc]
    @property
    def validation_errors(self) -> list[str]:
        """List of validation error messages (empty if valid)."""
        errors: list[str] = []
        if not self.phone_header:
            errors.append("No se ha mapeado ninguna cabecera como teléfono")
            return errors
        raw = self.phone_raw
        if not raw or not str(raw).strip():
            errors.append(
                f"La columna '{self.phone_header}' no tiene teléfono para esta fila"
            )
            return errors
        phone = self.phone_normalized
        if phone is None:
            errors.append("No se pudo normalizar el teléfono")
        elif not _E164_PATTERN.match(phone):
            errors.append(f"El teléfono normalizado no es válido: {phone}")
        return errors

    def get(self, header: str) -> str:
        """Return the cell value for ``header`` (case-insensitive), or ''."""
        target = header.strip().lower()
        for key, value in self.raw_data.items():
            if key.strip().lower() == target:
                return value
        return ""

    def model_dump_json_safe(self) -> dict:
        """Return a JSON-serializable dict without computed fields causing recursion."""
        data = self.model_dump(mode="json")
        return data
