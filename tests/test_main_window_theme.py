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

if HAS_PYSIDE6:
    from PySide6.QtWidgets import QApplication, QToolButton

    from canalyze.ui.main_window import MainWindow
else:
    QApplication = None


@unittest.skipUnless(HAS_PYSIDE6, "PySide6 is not installed")
class MainWindowThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._app = QApplication.instance() or QApplication([])

    def test_toggle_theme_updates_mode_and_button_state(self) -> None:
        window = MainWindow(
            loader=DatasetLoader(),
            decoder=DecoderService(),
            filter_engine=FilterEngine(),
            plot_builder=PlotModelBuilder(),
        )
        self.addCleanup(window.deleteLater)

        self.assertEqual(window._theme_mode, "light")
        self.assertIsInstance(window.theme_toggle_button, QToolButton)
        self.assertEqual(window.theme_toggle_button.toolTip(), "Switch to dark theme")
        self.assertFalse(window.theme_toggle_button.icon().isNull())

        window.toggle_theme()

        self.assertEqual(window._theme_mode, "dark")
        self.assertEqual(window.theme_toggle_button.toolTip(), "Switch to light theme")
        self.assertFalse(window.theme_toggle_button.icon().isNull())
        self.assertIn("#171a1f", window.styleSheet())
        self.assertEqual(window.plot_widget._axis_color, "#eef2f7")

        window.toggle_theme()

        self.assertEqual(window._theme_mode, "light")
        self.assertEqual(window.theme_toggle_button.toolTip(), "Switch to dark theme")
        self.assertIn("#f5f6f8", window.styleSheet())
        self.assertEqual(window.plot_widget._axis_color, "#1c1f24")


if __name__ == "__main__":
    unittest.main()
