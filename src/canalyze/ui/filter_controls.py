from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from canalyze.compat import HAS_PYSIDE6

if HAS_PYSIDE6:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
else:
    QWidget = object


@dataclass(slots=True)
class FilterOption:
    value: str
    display: str
    search_terms: tuple[str, ...]


class SearchableMultiSelectFilter(QWidget):
    def __init__(
        self,
        placeholder: str,
        normalizer: Callable[[str], str | None],
        resolver: Callable[[str, dict[str, FilterOption]], str | None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._normalizer = normalizer
        self._resolver = resolver
        self._options: dict[str, FilterOption] = {}
        self._selected_values: list[str] = []

        self._line_edit = QLineEdit(self)
        self._line_edit.setPlaceholderText(placeholder)
        self._line_edit.textEdited.connect(self._on_text_edited)
        self._line_edit.returnPressed.connect(self.commit_pending_input)

        self._toggle_button = QToolButton(self)
        self._toggle_button.setText("▾")
        self._toggle_button.setCursor(Qt.PointingHandCursor)
        self._toggle_button.clicked.connect(self._toggle_popup)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(6)
        input_row.addWidget(self._line_edit, stretch=1)
        input_row.addWidget(self._toggle_button)

        self._summary_label = QLabel("Any", self)
        self._summary_label.setWordWrap(True)
        self._summary_label.setObjectName("selectionSummary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(input_row)
        layout.addWidget(self._summary_label)

        self._popup = QFrame(self, Qt.Popup)
        self._popup.setObjectName("filterPopup")
        self._popup.setFrameShape(QFrame.Shape.StyledPanel)

        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setContentsMargins(4, 4, 4, 4)
        popup_layout.setSpacing(0)

        self._list_widget = QListWidget(self._popup)
        self._list_widget.itemClicked.connect(self._toggle_item_from_click)
        popup_layout.addWidget(self._list_widget)

        self._refresh_summary()

    def set_available_options(self, options: Iterable[FilterOption]) -> None:
        self._options = {option.value: option for option in options}
        self._refresh_popup_items(self._line_edit.text())
        self._refresh_summary()

    def selected_values(self) -> list[str]:
        self.commit_pending_input()
        return list(self._selected_values)

    def clear(self) -> None:
        self._selected_values.clear()
        self._line_edit.clear()
        self._popup.hide()
        self._refresh_popup_items("")
        self._refresh_summary()

    def commit_pending_input(self) -> None:
        raw_text = self._line_edit.text().strip()
        if not raw_text:
            return
        normalized = (
            self._resolver(raw_text, self._options)
            if self._resolver is not None
            else self._normalizer(raw_text)
        )
        if normalized is None:
            return
        self._add_selected_value(normalized)
        self._line_edit.clear()
        self._refresh_popup_items("")

    def _toggle_popup(self) -> None:
        if self._popup.isVisible():
            self._popup.hide()
            return
        self._show_popup(self._line_edit.text())

    def _on_text_edited(self, text: str) -> None:
        self._show_popup(text)

    def _show_popup(self, query: str) -> None:
        self._refresh_popup_items(query)
        self._popup.resize(max(self.width(), 240), 220)
        popup_position = self.mapToGlobal(QPoint(0, self.height()))
        self._popup.move(popup_position)
        self._popup.show()
        self._popup.raise_()

    def _refresh_popup_items(self, query: str) -> None:
        normalized_query = query.strip().lower()
        self._list_widget.clear()

        matches = [
            option
            for option in self._options.values()
            if not normalized_query
            or any(normalized_query in term for term in option.search_terms)
        ]
        for option in sorted(matches, key=lambda item: item.display.lower()):
            item = QListWidgetItem(option.display, self._list_widget)
            item.setData(Qt.ItemDataRole.UserRole, option.value)
            item.setCheckState(
                Qt.CheckState.Checked if option.value in self._selected_values else Qt.CheckState.Unchecked
            )

        if normalized_query and not matches:
            normalized_value = self._normalizer(query)
            if normalized_value and normalized_value not in self._options:
                add_item = QListWidgetItem(f'Add "{normalized_value}"', self._list_widget)
                add_item.setData(Qt.ItemDataRole.UserRole, normalized_value)
                add_item.setData(Qt.ItemDataRole.UserRole + 1, True)
                add_item.setCheckState(
                    Qt.CheckState.Checked
                    if normalized_value in self._selected_values
                    else Qt.CheckState.Unchecked
                )

    def _toggle_item_from_click(self, item: QListWidgetItem) -> None:
        value = item.data(Qt.ItemDataRole.UserRole)
        if not value:
            return
        if value in self._selected_values:
            self._selected_values.remove(value)
            item.setCheckState(Qt.CheckState.Unchecked)
        else:
            self._add_selected_value(value)
            item.setCheckState(Qt.CheckState.Checked)
        self._refresh_summary()
        self._line_edit.clear()
        self._refresh_popup_items("")
        self._show_popup("")

    def _add_selected_value(self, value: str) -> None:
        if value in self._selected_values:
            return
        self._selected_values.append(value)
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        if not self._selected_values:
            self._summary_label.setText("Any")
            return

        display_values = [
            self._options.get(value, FilterOption(value=value, display=value, search_terms=(value.lower(),))).display
            for value in self._selected_values
        ]
        self._summary_label.setText(", ".join(display_values))
