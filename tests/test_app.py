from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canalyze.app import _show_startup_failure, main


class AppStartupTests(unittest.TestCase):
    def test_main_reports_startup_failures(self) -> None:
        with (
            patch("canalyze.app._run_application", side_effect=RuntimeError("boom")),
            patch("canalyze.app._show_startup_failure") as show_startup_failure,
        ):
            self.assertEqual(main(), 1)
            show_startup_failure.assert_called_once()

    def test_show_startup_failure_reports_log_path_without_qt(self) -> None:
        with (
            patch("canalyze.app._write_startup_log", return_value=Path("C:/temp/startup-error.log")),
            patch("canalyze.app._import_qt_widgets", side_effect=ImportError("missing qt")),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            _show_startup_failure(RuntimeError("boom"))

        output = stderr.getvalue()
        self.assertIn("boom", output)
        self.assertIn("startup-error.log", output)


if __name__ == "__main__":
    unittest.main()
