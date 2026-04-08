from __future__ import annotations

from typing import Any

from canalyze.compat import HAS_PYSIDE6

if HAS_PYSIDE6:
    from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
else:
    QAbstractTableModel = object
    QModelIndex = object
    Qt = None


class FrameTableModel(QAbstractTableModel):
    columns = [
        ("timestamp", "Timestamp"),
        ("can_id_hex", "CAN ID"),
        ("dlc", "DLC"),
        ("data_hex", "Data"),
        ("message_name", "Message"),
    ]

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._rows = rows or []

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        if hasattr(self, "beginResetModel"):
            self.beginResetModel()
        self._rows = rows
        if hasattr(self, "endResetModel"):
            self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent and getattr(parent, "isValid", lambda: False)() else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent and getattr(parent, "isValid", lambda: False)() else len(self.columns)

    def data(self, index: QModelIndex, role: int = 0) -> Any:
        if not getattr(index, "isValid", lambda: False)():
            return None
        row = self._rows[index.row()]
        key, _ = self.columns[index.column()]
        if role == Qt.DisplayRole:
            value = row.get(key, "")
            if key == "timestamp" and isinstance(value, float):
                return f"{value:.6f}"
            return str(value)
        return None

    def headerData(self, section: int, orientation: int, role: int = 0) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.columns[section][1]
        return str(section + 1)

    def row_at(self, row: int) -> dict[str, Any]:
        return self._rows[row]
