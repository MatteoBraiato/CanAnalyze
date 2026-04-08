from __future__ import annotations

from dataclasses import dataclass

from canalyze.compat import HAS_PYSIDE6

if HAS_PYSIDE6:
    from PySide6.QtWidgets import (
        QDialog,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
else:
    QDialog = object


@dataclass(slots=True)
class StartupSelection:
    log_path: str
    dbc_path: str | None


class StartupDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CAN Log Analyzer")
        self.resize(560, 220)

        self.log_path_edit = QLineEdit(self)
        self.dbc_path_edit = QLineEdit(self)

        log_browse = QPushButton("Browse Log", self)
        log_browse.clicked.connect(self._browse_log)
        dbc_browse = QPushButton("Browse DBC", self)
        dbc_browse.clicked.connect(self._browse_dbc)

        form = QFormLayout()
        form.addRow("CAN log file", self._with_browse(self.log_path_edit, log_browse))
        form.addRow("DBC file", self._with_browse(self.dbc_path_edit, dbc_browse))

        load_button = QPushButton("Load Files", self)
        load_button.clicked.connect(self._accept_with_dbc)
        raw_only_button = QPushButton("Continue without DBC", self)
        raw_only_button.clicked.connect(self._accept_without_dbc)

        info_label = QLabel(
            "Load a CAN log file to start. DBC is optional and enables decoded messages and signal plotting.",
            self,
        )
        info_label.setWordWrap(True)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(raw_only_button)
        buttons.addWidget(load_button)

        layout = QVBoxLayout(self)
        layout.addWidget(info_label)
        layout.addLayout(form)
        layout.addStretch(1)
        layout.addLayout(buttons)

        self._selection: StartupSelection | None = None

    def selection(self) -> StartupSelection | None:
        return self._selection

    def _with_browse(self, line_edit, button):
        container = QHBoxLayout()
        container.setContentsMargins(0, 0, 0, 0)
        container.addWidget(line_edit)
        container.addWidget(button)
        wrapper = QWidget(self)
        wrapper.setLayout(container)
        return wrapper

    def _browse_log(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CAN log",
            "",
            "CAN Logs (*.asc *.trc);;All Files (*.*)",
        )
        if path:
            self.log_path_edit.setText(path)

    def _browse_dbc(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select DBC file",
            "",
            "DBC Files (*.dbc);;All Files (*.*)",
        )
        if path:
            self.dbc_path_edit.setText(path)

    def _accept_with_dbc(self) -> None:
        log_path = self.log_path_edit.text().strip()
        dbc_path = self.dbc_path_edit.text().strip() or None
        if not log_path:
            return
        self._selection = StartupSelection(log_path=log_path, dbc_path=dbc_path)
        self.accept()

    def _accept_without_dbc(self) -> None:
        log_path = self.log_path_edit.text().strip()
        if not log_path:
            return
        self._selection = StartupSelection(log_path=log_path, dbc_path=None)
        self.accept()
