from __future__ import annotations

from canalyze.compat import HAS_PYSIDE6
from canalyze.services.dbc import DbcConflict

if HAS_PYSIDE6:
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )
else:
    QDialog = object


class DbcConflictResolutionDialog(QDialog):
    def __init__(self, conflicts: list[DbcConflict], parent=None, theme_name: str = "dark") -> None:
        super().__init__(parent)
        self.setWindowTitle("Resolve DBC Signal Conflicts")
        self._selectors: dict[tuple[str, tuple[str, ...]], QComboBox] = {}
        self._theme_name = theme_name

        title = QLabel("Resolve overlapping DBC signals", self)
        title.setObjectName("dialogTitle")

        intro = QLabel(
            "Choose which signal to keep for each overlap. Selecting Ignore Both removes both "
            "conflicting signals from decoding for that message.",
            self,
        )
        intro.setWordWrap(True)
        intro.setObjectName("dialogIntro")

        summary = QLabel(f"{len(conflicts)} conflict pair(s) require a decision.", self)
        summary.setObjectName("dialogSummary")

        rows_host = QWidget(self)
        rows_layout = QVBoxLayout(rows_host)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(10)

        for conflict in conflicts:
            rows_layout.addWidget(self._build_conflict_row(conflict))
        rows_layout.addStretch(1)

        scroller = QScrollArea(self)
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.Shape.NoFrame)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroller.setWidget(rows_host)
        scroller.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.setObjectName("dialogButtons")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addWidget(summary)
        layout.addWidget(scroller, stretch=1)
        layout.addWidget(buttons)

        self.set_theme(theme_name)
        self._fit_to_content(len(conflicts))

    def selections(self) -> dict[tuple[str, tuple[str, ...]], str | None]:
        return {
            conflict_key: selector.currentData()
            for conflict_key, selector in self._selectors.items()
        }

    def set_theme(self, theme_name: str) -> None:
        self._theme_name = theme_name
        if theme_name == "light":
            colors = {
                "background": "#f5f6f8",
                "text": "#1c1f24",
                "muted": "#5f6b7a",
                "card": "#ffffff",
                "border": "#c9ced6",
                "button": "#e7ebf0",
                "button_hover": "#dbe2ea",
                "input": "#ffffff",
            }
        else:
            colors = {
                "background": "#171a1f",
                "text": "#eef2f7",
                "muted": "#aeb9c7",
                "card": "#20242c",
                "border": "#475264",
                "button": "#29303a",
                "button_hover": "#313949",
                "input": "#20242c",
            }

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {colors["background"]};
                color: {colors["text"]};
            }}
            QLabel {{
                color: {colors["text"]};
            }}
            QLabel#dialogTitle {{
                font-size: 18px;
                font-weight: 700;
            }}
            QLabel#dialogIntro,
            QLabel#signalNames {{
                color: {colors["muted"]};
            }}
            QLabel#dialogSummary,
            QLabel#messageName {{
                font-weight: 600;
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: transparent;
            }}
            QFrame#conflictCard {{
                border: 1px solid {colors["border"]};
                border-radius: 8px;
                background-color: {colors["card"]};
            }}
            QComboBox {{
                background-color: {colors["input"]};
                color: {colors["text"]};
                border: 1px solid {colors["border"]};
                border-radius: 6px;
                padding: 4px 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors["card"]};
                color: {colors["text"]};
                border: 1px solid {colors["border"]};
                selection-background-color: {colors["button_hover"]};
            }}
            QDialogButtonBox QPushButton {{
                background-color: {colors["button"]};
                color: {colors["text"]};
                border: 1px solid {colors["border"]};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QDialogButtonBox QPushButton:hover {{
                background-color: {colors["button_hover"]};
            }}
            """
        )

    def _build_conflict_row(self, conflict: DbcConflict) -> QFrame:
        card = QFrame(self)
        card.setObjectName("conflictCard")

        message_label = QLabel(conflict.message_name, card)
        message_label.setObjectName("messageName")

        detail_label = QLabel("Conflicting signals: " + " vs ".join(conflict.signal_names), card)
        detail_label.setObjectName("signalNames")
        detail_label.setWordWrap(True)

        selector = QComboBox(card)
        selector.setMinimumWidth(210)
        selector.addItem("Ignore Both", None)
        for signal_name in conflict.signal_names:
            selector.addItem(f"Keep {signal_name}", signal_name)
        self._selectors[(conflict.message_name, conflict.signal_names)] = selector

        content_layout = QHBoxLayout(card)
        content_layout.setContentsMargins(14, 12, 14, 12)
        content_layout.setSpacing(16)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        text_layout.addWidget(message_label)
        text_layout.addWidget(detail_label)

        content_layout.addLayout(text_layout, stretch=1)
        content_layout.addWidget(selector, alignment=Qt.AlignmentFlag.AlignTop)
        return card

    def _fit_to_content(self, row_count: int) -> None:
        preferred_width = 780
        preferred_height = min(220 + (row_count * 86), 640)
        self.resize(QSize(preferred_width, preferred_height).expandedTo(self.minimumSizeHint()))
