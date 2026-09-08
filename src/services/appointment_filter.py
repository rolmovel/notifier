"""Appointment filtering — Excel-like column filters with date awareness.

The filter engine is schema-agnostic: it works against the ``raw_data`` mapping
stored on each :class:`Appointment`. A filter is defined by three pieces:

* ``column`` — the Excel header to filter on.
* ``operator`` — one of the operators in :data:`TEXT_OPERATORS` (for text
  columns) or :data:`DATE_OPERATORS` (for date columns).
* ``value`` — free-form text used by operators that need an argument (e.g.
  ``contains`` or ``before``).

Multiple filters are combined with AND semantics: an appointment must match
every active filter to be included.

Date columns are detected heuristically by attempting to parse the column's
non-empty cell values; if a configurable majority parse as dates the column is
treated as a date column and the date operators become available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable

from src.models.appointment import Appointment

# Text operators (apply to any column).
TEXT_OPERATORS = ("contains", "equals", "starts_with", "not_empty")
# Date operators (only available on detected date columns).
DATE_OPERATORS = ("today", "tomorrow", "this_week", "exact_date", "before", "after")

# Formats tried when parsing a cell value as a date, in priority order. The
# Excel reader stores real datetime cells as ISO strings (``isoformat(sep=" ")``)
# so ``datetime.fromisoformat`` handles those; the rest cover common textual
# date formats a user might type in a spreadsheet.
_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%d.%m.%Y",
)

# Minimum fraction of parseable non-empty values for a column to count as a
# date column.
_DATE_DETECTION_THRESHOLD = 0.5


def parse_date(value: str) -> datetime | None:
    """Best-effort parse of a cell string into a ``datetime``.

    Returns ``None`` if the value is empty or cannot be parsed with any of the
    known formats.
    """
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    # ISO format covers the reader's ``isoformat(sep=" ")`` output and plain
    # ISO dates alike.
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def is_date_column(appointments: list[Appointment], column: str, threshold: float = _DATE_DETECTION_THRESHOLD) -> bool:
    """Heuristically decide whether ``column`` holds date values.

    A column is a date column when at least ``threshold`` (default 50%) of its
    non-empty values parse as dates, and there is at least one non-empty value.
    """
    non_empty = 0
    parsed = 0
    for appt in appointments:
        raw = appt.get(column)
        if not raw.strip():
            continue
        non_empty += 1
        if parse_date(raw) is not None:
            parsed += 1
    if non_empty == 0:
        return False
    return (parsed / non_empty) >= threshold


@dataclass
class FilterCondition:
    """A single column filter."""

    column: str
    operator: str
    value: str = ""
    # Whether the column has been detected as a date column. Cached at creation
    # time so the matching logic knows which parser to use.
    is_date: bool = field(default=False)

    def matches(self, appointment: Appointment) -> bool:
        """Return ``True`` if ``appointment`` satisfies this filter."""
        cell = appointment.get(self.column)

        if self.operator == "not_empty":
            return cell.strip() != ""

        if self.operator in ("contains", "equals", "starts_with"):
            target = self.value.strip().lower()
            if not target:
                # An empty text filter matches everything.
                return True
            cell_l = cell.strip().lower()
            if self.operator == "contains":
                return target in cell_l
            if self.operator == "equals":
                return cell_l == target
            # starts_with
            return cell_l.startswith(target)

        # Date operators.
        cell_dt = parse_date(cell)
        if self.operator in ("today", "tomorrow", "this_week"):
            if cell_dt is None:
                return False
            cell_day = cell_dt.date()
            today = date.today()
            if self.operator == "today":
                return cell_day == today
            if self.operator == "tomorrow":
                return cell_day == today + timedelta(days=1)
            # this_week: Monday–Sunday of the current week.
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)
            return monday <= cell_day <= sunday

        # Date operators that need a value argument.
        ref = parse_date(self.value)
        if ref is None or cell_dt is None:
            return False
        if self.operator == "exact_date":
            return cell_dt.date() == ref.date()
        if self.operator == "before":
            return cell_dt.date() < ref.date()
        if self.operator == "after":
            return cell_dt.date() > ref.date()
        return False


def build_condition(
    column: str,
    operator: str,
    value: str,
    appointments: list[Appointment],
) -> FilterCondition:
    """Build a :class:`FilterCondition`, auto-detecting date columns."""
    is_date = is_date_column(appointments, column) if appointments else False
    return FilterCondition(column=column, operator=operator, value=value, is_date=is_date)


def apply_filters(
    appointments: list[Appointment],
    conditions: list[FilterCondition],
) -> list[Appointment]:
    """Return the subset of ``appointments`` matching every condition (AND)."""
    if not conditions:
        return list(appointments)
    return [a for a in appointments if all(c.matches(a) for c in conditions)]


def distinct_values(appointments: list[Appointment], column: str, limit: int = 1000) -> list[str]:
    """Return the distinct non-empty values for ``column``, preserving order."""
    seen: dict[str, None] = {}
    for appt in appointments:
        v = appt.get(column).strip()
        if v and v not in seen:
            seen[v] = None
            if len(seen) >= limit:
                break
    return list(seen.keys())


# Operator -> translated label, used by the UI.
OPERATOR_LABELS: dict[str, str] = {
    "contains": "Contiene",
    "equals": "Es igual a",
    "starts_with": "Empieza por",
    "not_empty": "No está vacío",
    "today": "Hoy",
    "tomorrow": "Mañana",
    "this_week": "Esta semana",
    "exact_date": "Fecha exacta",
    "before": "Antes de",
    "after": "Después de",
}


def operators_for(is_date: bool) -> list[str]:
    """Return the operator keys available for a column of the given type."""
    return list(DATE_OPERATORS) if is_date else list(TEXT_OPERATORS)


def label_for(operator: str) -> str:
    """Return the Spanish label for an operator key."""
    return OPERATOR_LABELS.get(operator, operator)


# Type alias for the callback the UI uses to be notified of filter changes.
FilterChangedCallback = Callable[[], None]
