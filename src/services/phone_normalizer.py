"""Phone normalizer — convert phone numbers to E.164 format using libphonenumber."""

from __future__ import annotations

from typing import Optional

import phonenumbers


def normalize_phone(raw_phone: str, default_country_code: str = "+34") -> Optional[str]:
    """Normalize a phone number to E.164 format.

    Uses the phonenumbers library (Google libphonenumber port) to parse
    and validate phone numbers.

    Args:
        raw_phone: Raw phone string from Excel (may have spaces, dashes, etc.)
        default_country_code: Default country code (e.g., "+34" for Spain).

    Returns:
        E.164 formatted phone string (e.g., "+34612345678") or None if unparseable.
    """
    if not raw_phone:
        return None

    # Clean the input: remove whitespace, dashes, dots, parentheses
    cleaned = str(raw_phone).strip()
    if not cleaned:
        return None

    # Convert country code like "+34" to ISO 3166 region code for phonenumbers
    country_code_map = {
        "+34": "ES",
        "+1": "US",
        "+44": "GB",
        "+33": "FR",
        "+49": "DE",
        "+39": "IT",
        "+351": "PT",
        "+52": "MX",
        "+55": "BR",
        "+57": "CO",
        "+54": "AR",
        "+56": "CL",
        "+51": "PE",
        "+58": "VE",
        "+598": "UY",
        "+506": "CR",
    }

    region_code = country_code_map.get(default_country_code, "ES")

    try:
        # If the number already starts with +, parse as international
        if cleaned.startswith("+"):
            parsed = phonenumbers.parse(cleaned, None)
        else:
            # Strip leading zeros and try with the default region
            parsed = phonenumbers.parse(cleaned, region_code)

        # Check if the number is valid
        if not phonenumbers.is_valid_number(parsed):
            # Try possible number (some valid numbers fail strict validation)
            if not phonenumbers.is_possible_number(parsed):
                return None

        # Format to E.164
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return e164

    except phonenumbers.NumberParseException:
        return None
