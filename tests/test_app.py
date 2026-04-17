from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canalyze.app import (
    APP_USER_MODEL_ID,
    SMOKE_TEST_ENV_VAR,
    STARTUP_LOG_PATH_ENV_VAR,
    _create_app_icon,
    _configure_runtime_environment,
    _is_smoke_test_mode,
    _resolve_app_icon_paths,
    _resolve_app_icon_path,
    _startup_log_path,
    _run_smoke_test,
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

    def test_resolve_app_icon_paths_prefers_windows_ico_then_png(self) -> None:
        with patch("canalyze.app.sys.platform", "win32"):
            icon_paths = _resolve_app_icon_paths()

        self.assertGreaterEqual(len(icon_paths), 2)
        self.assertEqual([path.suffix for path in icon_paths[:2]], [".ico", ".png"])

    def test_resolve_app_icon_paths_uses_frozen_application_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            icon_dir = root / "icon"
            icon_dir.mkdir()
            png_path = icon_dir / "icon.png"
            ico_path = icon_dir / "icon.ico"
            png_path.write_bytes(b"png")
            ico_path.write_bytes(b"ico")

            with (
                patch("canalyze.app.sys.platform", "win32"),
                patch("canalyze.app._application_root", return_value=root),
            ):
                icon_paths = _resolve_app_icon_paths()

        self.assertEqual(icon_paths, [ico_path, png_path])

    def test_create_app_icon_adds_all_available_icon_files(self) -> None:
        class FakeIcon:
            def __init__(self) -> None:
                self.files: list[str] = []

            def addFile(self, path: str) -> None:
                self.files.append(path)

            def isNull(self) -> bool:
                return False

        icon_paths = [Path("icon/icon.ico"), Path("icon/icon.png")]

        with patch("canalyze.app._resolve_app_icon_paths", return_value=icon_paths):
            app_icon = _create_app_icon(FakeIcon)

        self.assertIsNotNone(app_icon)
        assert app_icon is not None
        self.assertEqual(app_icon.files, [str(path) for path in icon_paths])

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

    def test_startup_log_path_honors_environment_override(self) -> None:
        overridden_path = Path("/tmp/custom-startup.log")
        with patch.dict("os.environ", {STARTUP_LOG_PATH_ENV_VAR: str(overridden_path)}, clear=False):
            self.assertEqual(_startup_log_path(), overridden_path)

    def test_show_startup_failure_is_non_interactive_in_smoke_test_mode(self) -> None:
        with (
            patch.dict("os.environ", {SMOKE_TEST_ENV_VAR: "1"}, clear=False),
            patch("canalyze.app._write_startup_log", return_value=Path("C:/temp/smoke-startup.log")),
            patch("canalyze.app._import_qt_widgets") as import_qt_widgets,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            _show_startup_failure(RuntimeError("boom"))

        import_qt_widgets.assert_not_called()
        output = stderr.getvalue()
        self.assertIn("boom", output)
        self.assertIn("smoke-startup.log", output)

    def test_is_smoke_test_mode_reads_environment(self) -> None:
        with patch.dict("os.environ", {SMOKE_TEST_ENV_VAR: "1"}, clear=False):
            self.assertTrue(_is_smoke_test_mode())

    def test_configure_runtime_environment_pins_pyqtgraph_to_pyside6(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            _configure_runtime_environment()
            self.assertEqual(os.environ["PYQTGRAPH_QT_LIB"], "PySide6")

    def test_run_application_exits_cleanly_in_smoke_test_mode(self) -> None:
        class FakeApp:
            def setApplicationName(self, _name):
                pass

            def setApplicationVersion(self, _version):
                pass

            def setWindowIcon(self, _icon):
                pass

            def processEvents(self):
                pass

        class FakeIcon:
            def __init__(self) -> None:
                self._is_null = False
                self.files: list[str] = []

            def addFile(self, path: str) -> None:
                self.files.append(path)

            def isNull(self) -> bool:
                return self._is_null

        class FakePlotWidget:
            def __init__(self) -> None:
                self._plot_widget = object()
                self.deleted = False

            def deleteLater(self) -> None:
                self.deleted = True

        fake_plot_widget_module = type(
            "FakePlotWidgetModule",
            (),
            {
                "MultiAxisPlotWidget": FakePlotWidget,
                "get_plotting_unavailable_reason": staticmethod(lambda: None),
            },
        )

        with (
            patch.dict("os.environ", {SMOKE_TEST_ENV_VAR: "1"}, clear=False),
            patch("canalyze.app._import_qt_widgets", return_value=(lambda *_args: FakeApp(), object(), object())),
            patch("canalyze.app._import_qt_icon", return_value=FakeIcon),
            patch("canalyze.app._import_application_components", return_value=(object(), object(), object(), object(), object(), object())),
            patch("canalyze.app._import_plot_widget_module", return_value=fake_plot_widget_module),
            patch("canalyze.app._configure_runtime_environment"),
            patch("canalyze.app._set_windows_app_user_model_id"),
            patch("canalyze.app._resolve_app_icon_paths", return_value=[Path("icon/icon.ico"), Path("icon/icon.png")]),
        ):
            self.assertEqual(_run_application(), 0)

    def test_run_smoke_test_fails_when_plotting_is_unavailable(self) -> None:
        class FakeApp:
            def processEvents(self):
                pass

        class PlaceholderPlotWidget:
            def __init__(self) -> None:
                self._plot_widget = None

            def deleteLater(self) -> None:
                pass

        fake_plot_widget_module = type(
            "FakePlotWidgetModule",
            (),
            {
                "MultiAxisPlotWidget": PlaceholderPlotWidget,
                "get_plotting_unavailable_reason": staticmethod(
                    lambda: "No module named 'PySide6.QtOpenGLWidgets'"
                ),
            },
        )

        with patch("canalyze.app._import_plot_widget_module", return_value=fake_plot_widget_module):
            with self.assertRaisesRegex(
                RuntimeError,
                "Underlying error: No module named 'PySide6.QtOpenGLWidgets'",
            ):
                _run_smoke_test(FakeApp())


if __name__ == "__main__":
    unittest.main()
