from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from canalyze.compat import HAS_PYSIDE6

if HAS_PYSIDE6:
    from PySide6.QtWidgets import QApplication

    from canalyze.ui.filter_controls import FilterOption, SearchableMultiSelectFilter
else:
    QApplication = None


@unittest.skipUnless(HAS_PYSIDE6, "PySide6 is not installed")
class SearchableMultiSelectFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._app = QApplication.instance() or QApplication([])

    def test_filter_supports_manual_entry_and_selected_summary(self) -> None:
        widget = SearchableMultiSelectFilter(
            "Type or pick CAN IDs",
            normalizer=lambda text: text.strip() or None,
        )
        self.addCleanup(widget.deleteLater)

        widget.set_available_options(
            [
                FilterOption(value="A", display="Alpha", search_terms=("alpha",)),
                FilterOption(value="B", display="Beta", search_terms=("beta",)),
            ]
        )
        widget._line_edit.setText("B")
        widget.commit_pending_input()

        self.assertEqual(widget.selected_values(), ["B"])
        self.assertEqual(widget._summary_label.text(), "Beta")

    def test_filter_popup_list_is_filtered_by_typed_query(self) -> None:
        widget = SearchableMultiSelectFilter(
            "Type or pick message names",
            normalizer=lambda text: text.strip() or None,
        )
        self.addCleanup(widget.deleteLater)

        widget.set_available_options(
            [
                FilterOption(value="EngineData", display="EngineData", search_terms=("enginedata",)),
                FilterOption(value="BrakeData", display="BrakeData", search_terms=("brakedata",)),
            ]
        )
        widget._refresh_popup_items("br")

        self.assertEqual(widget._list_widget.count(), 1)
        self.assertEqual(widget._list_widget.item(0).text(), "BrakeData")


if __name__ == "__main__":
    unittest.main()
