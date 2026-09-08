"""Excel column mapper — build a header index for exact, case-insensitive lookup.

The Excel file is decoupled from the system: any schema is accepted as long as
it has a header row. Templates are resolved against the original header names
(see ``template_renderer``), so this module only provides a way to locate a
column by its exact header name (case-insensitive, ignoring surrounding
whitespace) and a helper to check that a header row is present.
"""

from __future__ import annotations


def has_header_row(headers: list[str]) -> bool:
    """Return True if ``headers`` contains at least one non-empty cell."""
    return any(str(h).strip() for h in headers)


def build_header_index(headers: list[str]) -> dict[str, int]:
    """Build a case-insensitive ``header_name -> column_index`` map.

    Lookup keys are the header names lowercased and stripped of surrounding
    whitespace, so callers can look up a column with ``index.get("start_time")``
    regardless of the original casing in the file.
    """
    index: dict[str, int] = {}
    for idx, header in enumerate(headers):
        key = str(header).strip().lower()
        if key and key not in index:
            index[key] = idx
    return index
