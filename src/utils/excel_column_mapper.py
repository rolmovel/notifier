"""Excel column mapper — normalize header names and match to canonical fields."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class ColumnMapping:
    """Result of mapping Excel headers to canonical fields."""

    mapping: dict[str, int] = field(default_factory=dict)
    missing_required: list[str] = field(default_factory=list)
    found_columns: list[str] = field(default_factory=list)


# Canonical fields and their accepted header names (already normalized)
CANONICAL_FIELDS: dict[str, dict] = {
    "start_time": {
        "required": True,
        "accepted": [
            "hora de inicio",
            "hora inicio",
            "hora",
            "inicio",
            "start time",
            "start_time",
            "fecha hora",
            "fecha y hora",
        ],
    },
    "duration": {
        "required": True,
        "accepted": [
            "duracion",
            "duracion min",
            "duracion minutos",
            "duration",
            "duration min",
            "duracion min",
            "minutos",
        ],
    },
    "gabinete": {
        "required": False,
        "accepted": [
            "gabinete",
            "ganinete",
            "gab",
            "sala",
            "consultorio",
            "consultorio",
        ],
    },
    "patient_name": {
        "required": True,
        "accepted": [
            "nombre del paciente",
            "paciente",
            "nombre",
            "patient name",
            "patient_name",
            "nombre paciente",
        ],
    },
    "appointment_type": {
        "required": True,
        "accepted": [
            "tipo de cita",
            "tipo cita",
            "tipo",
            "appointment type",
            "appointment_type",
            "tipo de consulta",
        ],
    },
    "phone_landline": {
        "required": False,
        "accepted": [
            "telefono fijo",
            "tel fijo",
            "fijo",
            "landline",
            "phone_landline",
            "telefono fijo",
            "fijo",
        ],
    },
    "phone_mobile": {
        "required": False,
        "accepted": [
            "telefono movil",
            "tel movil",
            "movil",
            "mobile",
            "phone_mobile",
            "telefono movil",
            "celular",
            "telefono celular",
        ],
    },
}


def normalize_header(header: str) -> str:
    """Normalize a header string for matching.

    - Lowercase
    - Strip accents (á → a, é → e, etc.)
    - Strip leading/trailing whitespace
    - Strip punctuation (except spaces)
    - Collapse multiple spaces
    """
    if header is None:
        return ""
    # Lowercase
    text = header.lower().strip()
    # Strip accents
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Strip punctuation (keep spaces and alphanumerics)
    text = re.sub(r"[^\w\s]", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def map_columns(headers: list[str]) -> ColumnMapping:
    """Map Excel header names to canonical field names.

    Args:
        headers: List of raw header strings from the Excel file (row 1).

    Returns:
        ColumnMapping with:
        - mapping: {canonical_field: column_index}
        - missing_required: list of required fields not found
        - found_columns: list of canonical fields that were found
    """
    result = ColumnMapping()

    # Build normalized header → index map
    normalized_headers: dict[str, int] = {}
    for idx, header in enumerate(headers):
        norm = normalize_header(str(header))
        if norm:
            normalized_headers[norm] = idx

    for canonical, config in CANONICAL_FIELDS.items():
        found = False
        for accepted in config["accepted"]:
            accepted_norm = normalize_header(accepted)
            if accepted_norm in normalized_headers:
                result.mapping[canonical] = normalized_headers[accepted_norm]
                result.found_columns.append(canonical)
                found = True
                break
        if not found and config["required"]:
            result.missing_required.append(canonical)

    return result
