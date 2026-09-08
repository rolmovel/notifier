"""Filter panel — Excel-like column filters with date quick-filters.

Provides a compact panel where the user can add one or more column filters.
Each filter row exposes the operators relevant to its column type:

* Text columns: Contiene / Es igual a / Empieza por / No está vacío.
* Date columns: Hoy / Mañana / Esta semana / Fecha exacta / Antes de / Después de.

The panel emits :pyattr:`filters_changed` whenever the active set of filters
changes so the host can re-apply them to the preview.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.models.appointment import Appointment
from src.services.appointment_filter import (
    DATE_OPERATORS,
    FilterCondition,
    build_condition,
    is_date_column,
    label_for,
    operators_for,
)

logger = logging.getLogger(__name__)


@dataclass
class FilterRowState:
    """Snapshot of a single filter row used to rebuild conditions."""

    column: str
    operator: str
    value: str = ""
    is_date: bool = False


class FilterRow(QWidget):
    """A single filter line: column + operator + value + remove button."""

    removed = Signal(object)  # emits itself

    def __init__(
        self,
        columns: list[str],
        date_columns: set[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._columns = list(columns)
        self._date_columns = set(date_columns)
        self._setup_ui()
        if self._columns:
            self._on_column_changed(self._columns[0])

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._column_combo = QComboBox()
        self._column_combo.addItems(self._columns)
        self._column_combo.currentTextChanged.connect(self._on_column_changed)
        layout.addWidget(self._column_combo, stretch=2)

        self._operator_combo = QComboBox()
        self._operator_combo.currentIndexChanged.connect(self._on_operator_changed)
        layout.addWidget(self._operator_combo, stretch=2)

        # Value input for text operators.
        self._value_edit = QLineEdit()
        self._value_edit.setPlaceholderText("Valor…")
        self._value_edit.textChanged.connect(self._emit_changed)
        layout.addWidget(self._value_edit, stretch=3)

        # Value input for date operators that take an argument.
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setDisplayFormat("dd/MM/yyyy")
        self._date_edit.dateChanged.connect(self._emit_changed)
        self._date_edit.setVisible(False)
        layout.addWidget(self._date_edit, stretch=3)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(28)
        remove_btn.setToolTip("Quitar filtro")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(remove_btn)

    def _is_date_column(self, column: str) -> bool:
        return column in self._date_columns

    def _on_column_changed(self, column: str) -> None:
        """Rebuild the operator list for the newly selected column."""
        is_date = self._is_date_column(column)
        self._operator_combo.blockSignals(True)
        self._operator_combo.clear()
        for op in operators_for(is_date):
            self._operator_combo.addItem(label_for(op), userData=op)
        self._operator_combo.blockSignals(False)
        # Default to the first operator and refresh the value widget.
        self._on_operator_changed(0)

    def _on_operator_changed(self, _index: int) -> None:
        """Show/hide the value input depending on the selected operator."""
        op = self._operator_combo.currentData() or ""
        needs_text = op in ("contains", "equals", "starts_with")
        needs_date = op in ("exact_date", "before", "after")
        self._value_edit.setVisible(needs_text)
        self._date_edit.setVisible(needs_date)
        self._emit_changed()

    def _emit_changed(self) -> None:
        # Bubble up via the parent panel (handled through filters_changed).
        panel = self.parent()
        while panel is not None and not isinstance(panel, FilterPanel):
            panel = panel.parent()
        if isinstance(panel, FilterPanel):
            panel._emit_changed()

    def state(self) -> FilterRowState:
        op = self._operator_combo.currentData() or ""
        value = ""
        if op in ("contains", "equals", "starts_with"):
            value = self._value_edit.text()
        elif op in ("exact_date", "before", "after"):
            value = self._date_edit.date().toString("yyyy-MM-dd")
        return FilterRowState(
            column=self._column_combo.currentText(),
            operator=op,
            value=value,
            is_date=self._is_date_column(self._column_combo.currentText()),
        )

    def set_columns(self, columns: list[str], date_columns: set[str]) -> None:
        """Update the available columns (e.g. after loading a new Excel file)."""
        self._columns = list(columns)
        self._date_columns = set(date_columns)
        current = self._column_combo.currentText()
        self._column_combo.blockSignals(True)
        self._column_combo.clear()
        self._column_combo.addItems(self._columns)
        if current in self._columns:
            self._column_combo.setCurrentText(current)
        elif self._columns:
            self._column_combo.setCurrentIndex(0)
        self._column_combo.blockSignals(False)
        self._on_column_changed(self._column_combo.currentText())


class FilterPanel(QWidget):
    """Panel holding zero or more :class:`FilterRow` instances."""

    filters_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns: list[str] = []
        self._date_columns: set[str] = set()
        self._rows: list[FilterRow] = []
        self._appointments: list[Appointment] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        title = QLabel("🔎 Filtros")
        title.setStyleSheet("font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self._add_btn = QPushButton("➕ Añadir filtro")
        self._add_btn.clicked.connect(self._on_add_filter)
        header.addWidget(self._add_btn)

        self._clear_btn = QPushButton("🧹 Limpiar")
        self._clear_btn.clicked.connect(self.clear_filters)
        header.addWidget(self._clear_btn)
        outer.addLayout(header)

        # Container for filter rows, inside a framed box so it reads as a unit.
        self._rows_frame = QFrame()
        self._rows_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._rows_layout = QVBoxLayout(self._rows_frame)
        self._rows_layout.setContentsMargins(6, 6, 6, 6)
        self._rows_layout.setSpacing(4)
        outer.addWidget(self._rows_frame)

        self._hint = QLabel("Sin filtros activos — se enviará a todas las filas.")
        self._hint.setStyleSheet("color: #888; font-size: 11px;")
        outer.addWidget(self._hint)

        self._refresh_hint()

    def set_appointments(self, appointments: list[Appointment]) -> None:
        """Refresh the available columns and date-column detection."""
        self._appointments = list(appointments)
        if appointments:
            self._columns = list(appointments[0].raw_data.keys())
            self._date_columns = {
                c for c in self._columns if c and is_date_column(self._appointments, c)
            }
        else:
            self._columns = []
            self._date_columns = set()
        self._add_btn.setEnabled(bool(self._columns))
        # Propagate to existing rows.
        for row in self._rows:
            row.set_columns(self._columns, self._date_columns)
        self._refresh_hint()

    def _on_add_filter(self) -> None:
        if not self._columns:
            return
        row = FilterRow(self._columns, self._date_columns, self._rows_frame)
        row.removed.connect(self._on_remove_row)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self._refresh_hint()
        self._emit_changed()

    def _on_remove_row(self, row: FilterRow) -> None:
        self._rows.remove(row)
        self._rows_layout.removeWidget(row)
        row.deleteLater()
        self._refresh_hint()
        self._emit_changed()

    def clear_filters(self) -> None:
        if not self._rows:
            return
        for row in list(self._rows):
            self._rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._refresh_hint()
        self._emit_changed()

    def _refresh_hint(self) -> None:
        if not self._columns:
            self._hint.setText("Carga un Excel para habilitar los filtros.")
        elif not self._rows:
            self._hint.setText("Sin filtros activos — se enviará a todas las filas.")
        else:
            self._hint.setText(
                f"{len(self._rows)} filtro(s) activo(s). "
                "Las filas que no cumplan se ocultan y no se envían."
            )

    def conditions(self) -> list[FilterCondition]:
        """Build the current filter conditions from the active rows."""
        result: list[FilterCondition] = []
        for row in self._rows:
            st = row.state()
            if not st.column:
                continue
            result.append(
                build_condition(st.column, st.operator, st.value, self._appointments)
            )
        return result

    def _emit_changed(self) -> None:
        self._refresh_hint()
        self.filters_changed.emit()
