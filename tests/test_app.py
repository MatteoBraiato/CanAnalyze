from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canalyze.app import (
    APP_USER_MODEL_ID,
    SMOKE_TEST_ENV_VAR,
    _is_smoke_test_mode,
    _resolve_app_icon_path,
    _set_windows_app_user_model_id,
    _show_startup_failure,
    _run_application,
    main,
)


class AppStartupTests(unittest.TestCase):
    def test_resolve_app_icon_path_returns_repo_icon(self) -> None:
        icon_path = _resolve_app_icon_path()

        self.assertIsNotNone(icon_path)
        assert icon_path is not None
        self.assertEqual(icon_path.name, "icon.png")
        self.assertTrue(icon_path.is_file())

    def test_set_windows_app_user_model_id_uses_expected_id(self) -> None:
        fake_shell32 = type("FakeShell32", (), {"calls": []})()

        def record_call(value):
            fake_shell32.calls.append(value)
            return 0

        fake_shell32.SetCurrentProcessExplicitAppUserModelID = record_call
        fake_ctypes = type("FakeCtypes", (), {"windll": type("Windll", (), {"shell32": fake_shell32})()})()

        with (
            patch("canalyze.app.sys.platform", "win32"),
            patch("canalyze.app.ctypes", fake_ctypes),
        ):
            _set_windows_app_user_model_id()

        self.assertEqual(fake_shell32.calls, [APP_USER_MODEL_ID])

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

    def test_is_smoke_test_mode_reads_environment(self) -> None:
        with patch.dict("os.environ", {SMOKE_TEST_ENV_VAR: "1"}, clear=False):
            self.assertTrue(_is_smoke_test_mode())

    def test_run_application_exits_cleanly_in_smoke_test_mode(self) -> None:
        class FakeApp:
            def setApplicationName(self, _name):
                pass

            def setApplicationVersion(self, _version):
                pass

            def setWindowIcon(self, _icon):
                pass

        class FakeIcon:
            def __init__(self, _path: str) -> None:
                self._is_null = False

            def isNull(self) -> bool:
                return self._is_null

        with (
            patch.dict("os.environ", {SMOKE_TEST_ENV_VAR: "1"}, clear=False),
            patch("canalyze.app._import_qt_widgets", return_value=(lambda *_args: FakeApp(), object(), object())),
            patch("canalyze.app._import_qt_icon", return_value=FakeIcon),
            patch("canalyze.app._import_application_components", return_value=(object(), object(), object(), object(), object(), object())),
            patch("canalyze.app._set_windows_app_user_model_id"),
            patch("canalyze.app._resolve_app_icon_path", return_value=Path("icon/icon.png")),
        ):
            self.assertEqual(_run_application(), 0)


if __name__ == "__main__":
    unittest.main()
