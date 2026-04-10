from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from canalyze.version import APP_NAME, __version__


def _startup_log_path() -> Path:
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


def _show_startup_failure(exc: BaseException) -> None:
    log_path = _write_startup_log(exc)
    detail_lines = [str(exc) or exc.__class__.__name__]
    if log_path is not None:
        detail_lines.append(f"Details were written to:\n{log_path}")
    message = "\n\n".join(detail_lines)

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
    QApplication, QMessageBox, QDialog = _import_qt_widgets()
    (
        DecoderService,
        FilterEngine,
        DatasetLoader,
        PlotModelBuilder,
        MainWindow,
        StartupDialog,
    ) = _import_application_components()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    loader = DatasetLoader()
    decoder = DecoderService()
    filter_engine = FilterEngine()
    plot_builder = PlotModelBuilder()

    startup = StartupDialog()
    if startup.exec() != QDialog.DialogCode.Accepted or startup.selection() is None:
        return 0

    selection = startup.selection()
    window = MainWindow(loader, decoder, filter_engine, plot_builder)
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
