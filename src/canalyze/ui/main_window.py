from __future__ import annotations

from pathlib import Path

from canalyze.compat import HAS_PYSIDE6
from canalyze.domain.dataset import FrameDataset
from canalyze.domain.models import FilterCriteria
from canalyze.services.decoder import DecoderService
from canalyze.services.filtering import FilterEngine
from canalyze.services.loader import DatasetLoader
from canalyze.services.plotting import PlotModelBuilder
from canalyze.ui.dbc_conflict_dialog import DbcConflictResolutionDialog
from canalyze.ui.models import FrameTableModel
from canalyze.ui.plot_widget import MultiAxisPlotWidget
from canalyze.ui.view_helpers import materialize_filtered_rows
from canalyze.ui.workers import FunctionWorker
from canalyze.version import APP_NAME, __version__

if HAS_PYSIDE6:
    from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QItemSelectionModel
    from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import (
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QSplitter,
        QStatusBar,
        QTableView,
        QToolBar,
        QToolButton,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
        QSizePolicy,
    )
else:
    QMainWindow = object


LIGHT_THEME_STYLESHEET = """
QWidget {
    background-color: #f5f6f8;
    color: #1c1f24;
}
QLineEdit, QPlainTextEdit, QTreeWidget, QTableView {
    background-color: #ffffff;
    color: #1c1f24;
    border: 1px solid #c9ced6;
}
QPushButton {
    background-color: #e7ebf0;
    color: #1c1f24;
    border: 1px solid #c9ced6;
    padding: 4px 10px;
}
QPushButton:hover {
    background-color: #dbe2ea;
}
QHeaderView::section {
    background-color: #e7ebf0;
    color: #1c1f24;
}
QStatusBar {
    background-color: #e7ebf0;
    color: #1c1f24;
}
""".strip()


DARK_THEME_STYLESHEET = """
QWidget {
    background-color: #171a1f;
    color: #eef2f7;
}
QLineEdit, QPlainTextEdit, QTreeWidget, QTableView {
    background-color: #20242c;
    color: #eef2f7;
    border: 1px solid #3c4452;
}
QPushButton {
    background-color: #29303a;
    color: #eef2f7;
    border: 1px solid #475264;
    padding: 4px 10px;
}
QPushButton:hover {
    background-color: #313949;
}
QHeaderView::section {
    background-color: #29303a;
    color: #eef2f7;
}
QStatusBar {
    background-color: #29303a;
    color: #eef2f7;
}
""".strip()


class MainWindow(QMainWindow):
    def __init__(
        self,
        loader: DatasetLoader,
        decoder: DecoderService,
        filter_engine: FilterEngine,
        plot_builder: PlotModelBuilder,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.loader = loader
        self.decoder = decoder
        self.filter_engine = filter_engine
        self.plot_builder = plot_builder

        self.dataset: FrameDataset | None = None
        self.filtered_indices: list[int] = []
        self.current_dbc_path: str | None = None
        self.dbc_database = None
        self._workers: list[FunctionWorker] = []
        self._pending_dbc_path: str | None = None
        self._theme_mode = "light"

        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(1440, 900)

        self._build_ui()
        self._apply_theme()
        self._set_status(f"No log loaded. Version {__version__}.")

    def load_log(self, log_path: str, dbc_path: str | None = None) -> None:
        self._set_status(f"Loading {Path(log_path).name}...")
        self._start_worker(self.loader.load, log_path, on_success=self._on_dataset_loaded)
        self._pending_dbc_path = dbc_path

    def _build_ui(self) -> None:
        self._build_toolbar()

        self.signal_tree = QTreeWidget(self)
        self.signal_tree.setHeaderLabels(["Messages / Signals"])
        self.signal_tree.itemChanged.connect(self._on_tree_item_changed)

        self.plot_widget = MultiAxisPlotWidget(self)

        top_splitter = QSplitter(Qt.Horizontal, self)
        top_splitter.addWidget(self.signal_tree)
        top_splitter.addWidget(self.plot_widget)
        top_splitter.setStretchFactor(1, 1)

        self.filter_can_ids = QLineEdit(self)
        self.filter_time_start = QLineEdit(self)
        self.filter_time_end = QLineEdit(self)
        self.filter_message_names = QLineEdit(self)
        apply_filter_button = QPushButton("Apply Filters", self)
        apply_filter_button.clicked.connect(self.apply_filters)
        clear_filter_button = QPushButton("Clear", self)
        clear_filter_button.clicked.connect(self.clear_filters)

        filter_form = QFormLayout()
        filter_form.addRow("CAN IDs", self.filter_can_ids)
        filter_form.addRow("Start time (s)", self.filter_time_start)
        filter_form.addRow("End time (s)", self.filter_time_end)
        filter_form.addRow("Message names", self.filter_message_names)

        filter_actions = QHBoxLayout()
        filter_actions.addStretch(1)
        filter_actions.addWidget(clear_filter_button)
        filter_actions.addWidget(apply_filter_button)

        filter_panel = QWidget(self)
        filter_panel_layout = QVBoxLayout(filter_panel)
        filter_panel_layout.setContentsMargins(0, 0, 0, 0)
        filter_panel_layout.addLayout(filter_form)
        filter_panel_layout.addLayout(filter_actions)

        self.table_model = FrameTableModel([])
        self.message_table = QTableView(self)
        self.message_table.setModel(self.table_model)
        self.message_table.setSelectionBehavior(QTableView.SelectRows)
        self.message_table.setSelectionMode(QTableView.SingleSelection)
        self.message_table.selectionModel().selectionChanged.connect(self._update_raw_inspector)
        self.message_table.setSortingEnabled(True)
        self.plot_widget.sampleActivated.connect(self._select_message_row_for_frame)

        self.raw_inspector = QPlainTextEdit(self)
        self.raw_inspector.setReadOnly(True)

        bottom_container = QWidget(self)
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(filter_panel)
        bottom_layout.addWidget(QLabel("Messages", self))
        bottom_layout.addWidget(self.message_table, stretch=3)
        bottom_layout.addWidget(QLabel("Raw frame inspector", self))
        bottom_layout.addWidget(self.raw_inspector, stretch=1)

        main_splitter = QSplitter(Qt.Vertical, self)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_container)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 2)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(main_splitter)
        self.setCentralWidget(container)

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_log = QPushButton("Open Log", self)
        open_log.clicked.connect(self._select_log)
        load_dbc = QPushButton("Load DBC", self)
        load_dbc.clicked.connect(self._select_dbc)
        clear_dbc = QPushButton("Unload DBC", self)
        clear_dbc.clicked.connect(self._clear_dbc)
        expand_tree = QPushButton("Expand All", self)
        expand_tree.clicked.connect(self.expand_signal_tree)
        collapse_tree = QPushButton("Collapse All", self)
        collapse_tree.clicked.connect(self.collapse_signal_tree)

        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.theme_toggle_button = QToolButton(self)
        self.theme_toggle_button.setAutoRaise(True)
        self.theme_toggle_button.setCursor(Qt.PointingHandCursor)
        self.theme_toggle_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.theme_toggle_button.setIconSize(QSize(22, 22))
        self.theme_toggle_button.clicked.connect(self.toggle_theme)

        toolbar.addWidget(open_log)
        toolbar.addWidget(load_dbc)
        toolbar.addWidget(clear_dbc)
        toolbar.addWidget(expand_tree)
        toolbar.addWidget(collapse_tree)
        toolbar.addWidget(spacer)
        toolbar.addWidget(self.theme_toggle_button)

    def _select_log(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CAN log",
            "",
            "CAN Logs (*.asc *.trc);;All Files (*.*)",
        )
        if path:
            self.load_log(path, self.current_dbc_path)

    def _select_dbc(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select DBC file",
            "",
            "DBC Files (*.dbc);;All Files (*.*)",
        )
        if path:
            self.current_dbc_path = path
            self._decode_current_dataset(path)

    def _clear_dbc(self) -> None:
        self.current_dbc_path = None
        self.dbc_database = None
        if self.dataset is not None:
            self.dataset.decoded_messages = []
            self.dataset.signal_samples = []
            rows = self._table_rows()
            self.dataset.frame_table = [
                {**row, "message_name": "", "decode_status": "not_decoded", "warning": ""}
                for row in rows
            ]
            self.filtered_indices = list(range(len(self.dataset.frames)))
            self._refresh_views()
        self._set_status("DBC unloaded. Raw mode active.")

    def _on_dataset_loaded(self, dataset: FrameDataset) -> None:
        self.dataset = dataset
        self.filtered_indices = list(range(len(dataset.frames)))
        self._refresh_views()
        self._set_status(f"Loaded {len(dataset.frames)} CAN frames.")
        if getattr(self, "_pending_dbc_path", None):
            self.current_dbc_path = self._pending_dbc_path
            self._decode_current_dataset(self.current_dbc_path)
        self._pending_dbc_path = None

    def _decode_current_dataset(self, dbc_path: str | None) -> None:
        if self.dataset is None or not dbc_path:
            return
        self._set_status(f"Decoding with {Path(dbc_path).name}...")
        try:
            conflicts = self.decoder.inspect_database_conflicts(dbc_path)
            pair_conflicts = [conflict for conflict in conflicts if len(conflict.signal_names) == 2]
            pair_conflict_choices = self._resolve_pair_conflicts(pair_conflicts)
            load_result = self.decoder.load_database(dbc_path, pair_conflict_choices)
        except Exception as exc:
            self._on_worker_failed(str(exc))
            return
        self.dbc_database = load_result.database
        self.dataset.warnings.extend(load_result.warnings)

        def _decode():
            return self.decoder.decode_dataset(self.dataset, self.dbc_database)

        self._start_worker(_decode, on_success=self._on_dataset_decoded)

    def _on_dataset_decoded(self, dataset: FrameDataset) -> None:
        self.dataset = dataset
        self.apply_filters()
        self._set_status(
            f"DBC decode complete. {len(dataset.signal_samples)} signal samples available."
        )

    def apply_filters(self) -> None:
        if self.dataset is None:
            return
        criteria = self._read_filter_criteria()
        self.filtered_indices = self.filter_engine.apply(self.dataset, criteria)
        self._refresh_views()
        self._set_status(f"{len(self.filtered_indices)} frames match current filters.")

    def clear_filters(self) -> None:
        self.filter_can_ids.clear()
        self.filter_time_start.clear()
        self.filter_time_end.clear()
        self.filter_message_names.clear()
        if self.dataset is not None:
            self.filtered_indices = list(range(len(self.dataset.frames)))
            self._refresh_views()
            self._set_status("Filters cleared.")

    def _read_filter_criteria(self) -> FilterCriteria:
        can_ids = None
        message_names = None

        raw_can_ids = [part.strip() for part in self.filter_can_ids.text().split(",") if part.strip()]
        if raw_can_ids:
            can_ids = {
                int(part, 16) if part.lower().startswith("0x") else int(part)
                for part in raw_can_ids
            }

        raw_message_names = [
            part.strip() for part in self.filter_message_names.text().split(",") if part.strip()
        ]
        if raw_message_names:
            message_names = set(raw_message_names)

        return FilterCriteria(
            can_ids=can_ids,
            time_start=float(self.filter_time_start.text()) if self.filter_time_start.text() else None,
            time_end=float(self.filter_time_end.text()) if self.filter_time_end.text() else None,
            message_names=message_names,
        )

    def _refresh_views(self) -> None:
        if self.dataset is None:
            return
        rows = materialize_filtered_rows(self._table_rows, self.filtered_indices)
        self.table_model.set_rows(rows)
        self._populate_signal_tree()
        self._refresh_plot()
        self._show_warnings()

    def _table_rows(self) -> list[dict]:
        if self.dataset is None:
            return []
        if isinstance(self.dataset.frame_table, list):
            return self.dataset.frame_table
        return self.dataset.frame_table.to_dict(orient="records")

    def _populate_signal_tree(self) -> None:
        self.signal_tree.blockSignals(True)
        self.signal_tree.clear()
        if self.dataset is None:
            self.signal_tree.blockSignals(False)
            return

        if not self.dataset.signal_samples:
            ids = sorted({self.dataset.frames[index].can_id for index in self.filtered_indices})
            for can_id in ids:
                QTreeWidgetItem(self.signal_tree, [f"0x{can_id:X}"])
            self.signal_tree.blockSignals(False)
            return

        allowed_keys = self.filter_engine.filtered_signal_keys(self.dataset, self.filtered_indices)
        message_nodes: dict[str, QTreeWidgetItem] = {}
        for message_name, signal_name in sorted(allowed_keys):
            message_item = message_nodes.get(message_name)
            if message_item is None:
                message_item = QTreeWidgetItem(self.signal_tree, [message_name])
                message_nodes[message_name] = message_item
            signal_item = QTreeWidgetItem(message_item, [signal_name])
            signal_item.setData(0, Qt.UserRole, (message_name, signal_name))
            signal_item.setFlags(signal_item.flags() | Qt.ItemIsUserCheckable)
            signal_item.setCheckState(0, Qt.Unchecked)
        self.signal_tree.expandAll()
        self.signal_tree.blockSignals(False)

    def _refresh_plot(self) -> None:
        if self.dataset is None:
            return
        selected = self._selected_signals()
        axis_groups = self.plot_builder.build(self.dataset, selected, self.filtered_indices)
        self.plot_widget.set_series(axis_groups)

    def _selected_signals(self) -> set[tuple[str, str]]:
        selected: set[tuple[str, str]] = set()
        root = self.signal_tree.invisibleRootItem()
        for index in range(root.childCount()):
            message_item = root.child(index)
            for child_index in range(message_item.childCount()):
                signal_item = message_item.child(child_index)
                if signal_item.checkState(0) == Qt.Checked:
                    selected.add(signal_item.data(0, Qt.UserRole))
        return selected

    def _on_tree_item_changed(self, item, _column: int) -> None:
        if item.childCount() == 0:
            self._refresh_plot()

    def expand_signal_tree(self) -> None:
        self.signal_tree.expandAll()

    def collapse_signal_tree(self) -> None:
        self.signal_tree.collapseAll()

    def toggle_theme(self) -> None:
        self._theme_mode = "dark" if self._theme_mode == "light" else "light"
        self._apply_theme()

    def _apply_theme(self) -> None:
        stylesheet = DARK_THEME_STYLESHEET if self._theme_mode == "dark" else LIGHT_THEME_STYLESHEET
        self.setStyleSheet(stylesheet)
        if hasattr(self, "theme_toggle_button"):
            self.theme_toggle_button.setIcon(self._theme_toggle_icon())
            self.theme_toggle_button.setToolTip(
                "Switch to light theme" if self._theme_mode == "dark" else "Switch to dark theme"
            )
            self.theme_toggle_button.setAccessibleName(
                "Light theme toggle" if self._theme_mode == "dark" else "Dark theme toggle"
            )
        if hasattr(self, "plot_widget"):
            self.plot_widget.set_theme(self._theme_mode)

    def _theme_toggle_icon(self) -> QIcon:
        return self._create_moon_icon() if self._theme_mode == "dark" else self._create_sun_icon()

    def _create_sun_icon(self) -> QIcon:
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#f4b400"))
        painter.drawEllipse(QRectF(7.0, 7.0, 10.0, 10.0))

        painter.setPen(QPen(QColor("#f4b400"), 1.8, Qt.SolidLine, Qt.RoundCap))
        for start, end in (
            (QPointF(12.0, 2.5), QPointF(12.0, 5.0)),
            (QPointF(12.0, 19.0), QPointF(12.0, 21.5)),
            (QPointF(2.5, 12.0), QPointF(5.0, 12.0)),
            (QPointF(19.0, 12.0), QPointF(21.5, 12.0)),
            (QPointF(5.2, 5.2), QPointF(7.0, 7.0)),
            (QPointF(17.0, 17.0), QPointF(18.8, 18.8)),
            (QPointF(5.2, 18.8), QPointF(7.0, 17.0)),
            (QPointF(17.0, 7.0), QPointF(18.8, 5.2)),
        ):
            painter.drawLine(start, end)
        painter.end()
        return QIcon(pixmap)

    def _create_moon_icon(self) -> QIcon:
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#eef2f7"))
        painter.drawEllipse(QRectF(5.0, 4.0, 14.0, 14.0))
        painter.setBrush(QColor("#171a1f"))
        painter.drawEllipse(QRectF(9.0, 3.0, 12.0, 14.0))
        painter.setBrush(QColor("#eef2f7"))
        painter.drawEllipse(QRectF(16.5, 6.0, 2.0, 2.0))
        painter.drawEllipse(QRectF(18.0, 10.0, 1.4, 1.4))
        painter.end()
        return QIcon(pixmap)

    def _update_raw_inspector(self, *_args) -> None:
        if self.dataset is None:
            return
        selected = self.message_table.selectionModel().selectedRows()
        if not selected:
            return
        visible_row = selected[0].row()
        dataset_index = self.filtered_indices[visible_row]
        frame = self.dataset.frames[dataset_index]
        byte_lines = []
        for index in range(8):
            if index < len(frame.data):
                value = frame.data[index]
                byte_lines.append(f"Byte {index}: 0x{value:02X} ({value})")
            else:
                byte_lines.append(f"Byte {index}: --")
        summary = [
            f"Timestamp: {frame.timestamp:.6f}s",
            f"CAN ID: 0x{frame.can_id:X}",
            f"DLC: {frame.dlc}",
            f"Direction: {frame.direction or '-'}",
            "",
            *byte_lines,
        ]
        self.raw_inspector.setPlainText("\n".join(summary))

    def _select_message_row_for_frame(self, frame_index: int) -> None:
        if self.dataset is None or frame_index not in self.filtered_indices:
            return

        visible_row = self.filtered_indices.index(frame_index)
        model_index = self.table_model.index(visible_row, 0)
        if not model_index.isValid():
            return

        selection_model = self.message_table.selectionModel()
        if selection_model is None:
            return

        selection_flags = (
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows
        )
        selection_model.select(model_index, selection_flags)
        self.message_table.setCurrentIndex(model_index)
        self.message_table.scrollTo(model_index, QTableView.ScrollHint.PositionAtCenter)
        self._update_raw_inspector()

    def _show_warnings(self) -> None:
        if self.dataset is None or not self.dataset.warnings:
            return
        latest = self.dataset.warnings[-1]
        self.statusBar().showMessage(latest.message, 8000)

    def _resolve_pair_conflicts(
        self,
        conflicts,
    ) -> dict[tuple[str, tuple[str, ...]], str | None]:
        if not conflicts:
            return {}

        dialog = DbcConflictResolutionDialog(conflicts, self)
        if dialog.exec():
            return dialog.selections()
        return {}

    def _start_worker(self, fn, *args, on_success) -> None:
        worker = FunctionWorker(fn, *args)
        worker.succeeded.connect(on_success)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        self._workers.append(worker)
        worker.start()

    def _on_worker_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Operation failed", message)
        self._set_status(message)

    def _set_status(self, message: str) -> None:
        self.statusBar().showMessage(message)
