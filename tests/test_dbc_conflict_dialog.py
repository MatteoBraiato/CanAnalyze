from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from canalyze.compat import HAS_PYSIDE6
from canalyze.services.dbc import DbcConflict

if HAS_PYSIDE6:
    from PySide6.QtWidgets import QApplication

    from canalyze.ui.dbc_conflict_dialog import DbcConflictResolutionDialog
else:
    QApplication = None


@unittest.skipUnless(HAS_PYSIDE6, "PySide6 is not installed")
class DbcConflictDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._app = QApplication.instance() or QApplication([])

    def test_dialog_sizes_to_content_and_preserves_selector_keys(self) -> None:
        dialog = DbcConflictResolutionDialog(
            [
                DbcConflict(message_name="EngineData", signal_names=("Speed", "Temp")),
                DbcConflict(message_name="BodyData", signal_names=("Door", "Window")),
            ]
        )
        self.addCleanup(dialog.deleteLater)

        selections = dialog.selections()

        self.assertEqual(
            set(selections),
            {
                ("EngineData", ("Speed", "Temp")),
                ("BodyData", ("Door", "Window")),
            },
        )
        self.assertGreaterEqual(dialog.width(), 780)
        self.assertGreaterEqual(dialog.height(), 220)


if __name__ == "__main__":
    unittest.main()
