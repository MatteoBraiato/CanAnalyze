from __future__ import annotations

from canalyze.compat import HAS_PYSIDE6
from canalyze.services.dbc import DbcConflict

if HAS_PYSIDE6:
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QGridLayout,
        QLabel,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )
else:
    QDialog = object


class DbcConflictResolutionDialog(QDialog):
    def __init__(self, conflicts: list[DbcConflict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resolve DBC Signal Conflicts")
        self.resize(920, 420)
        self._selectors: dict[tuple[str, tuple[str, ...]], QComboBox] = {}

        intro = QLabel(
            "Choose which signal to keep for each two-signal overlap. "
            "If you leave a row on Ignore Both, both conflicting signals will be dropped.",
            self,
        )
        intro.setWordWrap(True)

        grid_host = QWidget(self)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setColumnStretch(1, 1)
        grid.addWidget(QLabel("Message", self), 0, 0)
        grid.addWidget(QLabel("Conflicting Signals", self), 0, 1)
        grid.addWidget(QLabel("Resolution", self), 0, 2)

        for row, conflict in enumerate(conflicts, start=1):
            grid.addWidget(QLabel(conflict.message_name, self), row, 0)
            grid.addWidget(QLabel(" vs ".join(conflict.signal_names), self), row, 1)

            selector = QComboBox(self)
            selector.addItem("Ignore Both", None)
            for signal_name in conflict.signal_names:
                selector.addItem(f"Keep {signal_name}", signal_name)
            self._selectors[(conflict.message_name, conflict.signal_names)] = selector
            grid.addWidget(selector, row, 2)

        scroller = QScrollArea(self)
        scroller.setWidgetResizable(True)
        scroller.setWidget(grid_host)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(scroller, stretch=1)
        layout.addWidget(buttons)

    def selections(self) -> dict[tuple[str, tuple[str, ...]], str | None]:
        return {
            conflict_key: selector.currentData()
            for conflict_key, selector in self._selectors.items()
        }
