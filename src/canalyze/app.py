from __future__ import annotations

import ctypes
import os
import sys
import traceback
from pathlib import Path

from canalyze.version import APP_NAME, __version__

APP_USER_MODEL_ID = "MatteoBraiatoLTE.CanAnalyze"
SMOKE_TEST_ENV_VAR = "CANALYZE_SMOKE_TEST"
STARTUP_LOG_PATH_ENV_VAR = "CANALYZE_STARTUP_LOG_PATH"


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _resolve_app_icon_paths() -> list[Path]:
    icon_dir = _application_root() / "icon"
    icon_paths = {
        "png": icon_dir / "icon.png",
        "ico": icon_dir / "icon.ico",
    }

    ordered_suffixes = ["ico", "png"] if sys.platform == "win32" else ["png", "ico"]
    resolved_paths: list[Path] = []
    for suffix in ordered_suffixes:
        icon_path = icon_paths[suffix]
        if icon_path.is_file():
            resolved_paths.append(icon_path)
    return resolved_paths


def _resolve_app_icon_path() -> Path | None:
    icon_paths = _resolve_app_icon_paths()
    if not icon_paths:
        return None
    return icon_paths[0]


def _create_app_icon(QIcon) -> object | None:
    icon_paths = _resolve_app_icon_paths()
    if not icon_paths:
        return None

    app_icon = QIcon()
    for icon_path in icon_paths:
        app_icon.addFile(str(icon_path))

    if app_icon.isNull():
        return None

    return app_icon


def _is_smoke_test_mode() -> bool:
    return os.environ.get(SMOKE_TEST_ENV_VAR) == "1"


def _configure_runtime_environment() -> None:
    os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"


def _set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        return


def _startup_log_path() -> Path:
    overridden_log_path = os.environ.get(STARTUP_LOG_PATH_ENV_VAR)
    if overridden_log_path:
        log_path = Path(overridden_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return log_path

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base_dir = Path(local_app_data)
    else:
        base_dir = Path.home() / ".canalyze"

    log_dir = base_dir / "CanAnalyze"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "startup-error.log"


def _write_startup_log(exc: BaseException) -> Path | None:
    try:
        log_path = _startup_log_path()
        log_path.write_text(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            encoding="utf-8",
        )
        return log_path
    except Exception:
        return None


def _import_qt_widgets():
    from PySide6.QtWidgets import QApplication, QMessageBox, QDialog

    return QApplication, QMessageBox, QDialog


def _import_qt_icon():
    from PySide6.QtGui import QIcon

    return QIcon


def _import_application_components():
    from canalyze.services.decoder import DecoderService
    from canalyze.services.filtering import FilterEngine
    from canalyze.services.loader import DatasetLoader
    from canalyze.services.plotting import PlotModelBuilder
    from canalyze.ui.main_window import MainWindow
    from canalyze.ui.startup_dialog import StartupDialog

    return (
        DecoderService,
        FilterEngine,
        DatasetLoader,
        PlotModelBuilder,
        MainWindow,
        StartupDialog,
    )


def _import_plot_widget_module():
    from canalyze.ui import plot_widget

    return plot_widget


def _build_plotting_unavailable_message(plot_widget_module) -> str:
    message = "pyqtgraph plotting support is unavailable in the packaged application."
    detail = getattr(plot_widget_module, "get_plotting_unavailable_reason", lambda: None)()
    if detail:
        return f"{message} Underlying error: {detail}"
    return message


def _run_smoke_test(app) -> int:
    _configure_runtime_environment()
    plot_widget_module = _import_plot_widget_module()
    plot_widget = plot_widget_module.MultiAxisPlotWidget()
    try:
        if getattr(plot_widget, "_plot_widget", None) is None:
            raise RuntimeError(_build_plotting_unavailable_message(plot_widget_module))
        return 0
    finally:
        plot_widget.deleteLater()
        app.processEvents()


def _show_startup_failure(exc: BaseException) -> None:
    log_path = _write_startup_log(exc)
    detail_lines = [str(exc) or exc.__class__.__name__]
    if log_path is not None:
        detail_lines.append(f"Details were written to:\n{log_path}")
    message = "\n\n".join(detail_lines)

    if _is_smoke_test_mode():
        print(message, file=sys.stderr)
        return

    try:
        QApplication, QMessageBox, _QDialog = _import_qt_widgets()
    except Exception:
        print(message, file=sys.stderr)
        return

    try:
        app = QApplication.instance()
        created_app = False
        if app is None:
            app = QApplication(sys.argv)
            created_app = True
        QMessageBox.critical(None, "Startup failed", message)
        if created_app:
            app.quit()
        return
    except Exception:
        print(message, file=sys.stderr)


def _run_application() -> int:
    _configure_runtime_environment()
    QApplication, QMessageBox, QDialog = _import_qt_widgets()
    QIcon = _import_qt_icon()

    (
        DecoderService,
        FilterEngine,
        DatasetLoader,
        PlotModelBuilder,
        MainWindow,
        StartupDialog,
    ) = _import_application_components()

    _set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app_icon = _create_app_icon(QIcon)
    if app_icon is not None and not app_icon.isNull():
        app.setWindowIcon(app_icon)

    if _is_smoke_test_mode():
        return _run_smoke_test(app)

    loader = DatasetLoader()
    decoder = DecoderService()
    filter_engine = FilterEngine()
    plot_builder = PlotModelBuilder()

    startup = StartupDialog()
    if app_icon is not None and not app_icon.isNull():
        startup.setWindowIcon(app_icon)
    if startup.exec() != QDialog.DialogCode.Accepted or startup.selection() is None:
        return 0

    selection = startup.selection()
    window = MainWindow(loader, decoder, filter_engine, plot_builder)
    if app_icon is not None and not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()
    try:
        window.load_log(selection.log_path, selection.dbc_path)
    except Exception as exc:
        QMessageBox.critical(window, "Startup failed", str(exc))
        return 1
    return app.exec()


def main() -> int:
    try:
        return _run_application()
    except Exception as exc:
        _show_startup_failure(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
