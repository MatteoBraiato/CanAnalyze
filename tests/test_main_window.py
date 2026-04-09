from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from canalyze.compat import HAS_PYSIDE6
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


if __name__ == "__main__":
    unittest.main()
