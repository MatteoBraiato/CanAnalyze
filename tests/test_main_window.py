from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from canalyze.compat import HAS_PYSIDE6
from canalyze.domain.dataset import FrameDataset
from canalyze.domain.models import CANFrame
from canalyze.services.decoder import DecoderService
from canalyze.services.filtering import FilterEngine
from canalyze.services.loader import DatasetLoader
from canalyze.services.plotting import PlotModelBuilder
from canalyze.version import __version__

if HAS_PYSIDE6:
    from PySide6.QtWidgets import QApplication, QTreeWidgetItem

    from canalyze.ui.main_window import MainWindow
else:
    QApplication = None


@unittest.skipUnless(HAS_PYSIDE6, "PySide6 is not installed")
class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._app = QApplication.instance() or QApplication([])

    def test_expand_and_collapse_signal_tree(self) -> None:
        window = MainWindow(
            loader=DatasetLoader(),
            decoder=DecoderService(),
            filter_engine=FilterEngine(),
            plot_builder=PlotModelBuilder(),
        )
        self.addCleanup(window.deleteLater)

        message_item = QTreeWidgetItem(window.signal_tree, ["Message"])
        QTreeWidgetItem(message_item, ["Signal A"])
        QTreeWidgetItem(message_item, ["Signal B"])

        window.expand_signal_tree()
        self.assertTrue(message_item.isExpanded())

        window.collapse_signal_tree()
        self.assertFalse(message_item.isExpanded())

    def test_window_title_includes_version(self) -> None:
        window = MainWindow(
            loader=DatasetLoader(),
            decoder=DecoderService(),
            filter_engine=FilterEngine(),
            plot_builder=PlotModelBuilder(),
        )
        self.addCleanup(window.deleteLater)

        self.assertIn(__version__, window.windowTitle())

    def test_select_message_row_for_frame_updates_selection_and_raw_inspector(self) -> None:
        window = MainWindow(
            loader=DatasetLoader(),
            decoder=DecoderService(),
            filter_engine=FilterEngine(),
            plot_builder=PlotModelBuilder(),
        )
        self.addCleanup(window.deleteLater)

        window.dataset = FrameDataset.from_frames(
            [
                CANFrame(timestamp=0.1, can_id=0x100, dlc=2, data=bytes([0x01, 0x02])),
                CANFrame(timestamp=0.2, can_id=0x200, dlc=2, data=bytes([0xAA, 0xBB])),
            ]
        )
        window.filtered_indices = [0, 1]
        window._refresh_views()

        window._select_message_row_for_frame(1)

        selected_rows = window.message_table.selectionModel().selectedRows()
        self.assertEqual(len(selected_rows), 1)
        self.assertEqual(selected_rows[0].row(), 1)
        self.assertIn("CAN ID: 0x200", window.raw_inspector.toPlainText())

    def test_message_table_uses_wide_columns_and_row_readability_settings(self) -> None:
        window = MainWindow(
            loader=DatasetLoader(),
            decoder=DecoderService(),
            filter_engine=FilterEngine(),
            plot_builder=PlotModelBuilder(),
        )
        self.addCleanup(window.deleteLater)

        window.dataset = FrameDataset.from_frames(
            [
                CANFrame(
                    timestamp=12.345678,
                    can_id=0x18FF50E5,
                    dlc=8,
                    data=bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x01, 0x02]),
                )
            ]
        )
        window.filtered_indices = [0]
        window._refresh_views()

        self.assertFalse(window.message_table.showGrid())
        self.assertGreaterEqual(window.message_table.columnWidth(0), 130)
        self.assertGreaterEqual(window.message_table.columnWidth(3), 230)
        self.assertIn("QTableView::item:selected:active", window.message_table.styleSheet())

    def test_filter_controls_build_searchable_multi_select_criteria(self) -> None:
        window = MainWindow(
            loader=DatasetLoader(),
            decoder=DecoderService(),
            filter_engine=FilterEngine(),
            plot_builder=PlotModelBuilder(),
        )
        self.addCleanup(window.deleteLater)

        window.dataset = FrameDataset.from_frames(
            [
                CANFrame(timestamp=0.1, can_id=0x100, dlc=2, data=bytes([0x01, 0x02])),
                CANFrame(timestamp=0.2, can_id=0x200, dlc=2, data=bytes([0x03, 0x04])),
            ]
        )
        window.dataset.decoded_messages = [
            type("Decoded", (), {"message_name": "EngineData"})(),
            type("Decoded", (), {"message_name": "BrakeData"})(),
        ]
        window.filtered_indices = [0, 1]
        window._refresh_views()

        window.filter_can_ids._line_edit.setText("256")
        window.filter_message_names._line_edit.setText("EngineData")
        window.filter_can_ids._refresh_popup_items("20")

        self.assertEqual(window.filter_can_ids._list_widget.count(), 1)
        self.assertEqual(window.filter_can_ids._list_widget.item(0).text(), "0x200")

        criteria = window._read_filter_criteria()

        self.assertEqual(criteria.can_ids, {0x100})
        self.assertEqual(criteria.message_names, {"EngineData"})


if __name__ == "__main__":
    unittest.main()
