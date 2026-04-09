from __future__ import annotations

import sys

from canalyze.compat import HAS_PYSIDE6
from canalyze.services.decoder import DecoderService
from canalyze.services.filtering import FilterEngine
from canalyze.services.loader import DatasetLoader
from canalyze.services.plotting import PlotModelBuilder
from canalyze.version import APP_NAME, __version__

if HAS_PYSIDE6:
    from PySide6.QtWidgets import QApplication, QMessageBox, QDialog

    from canalyze.ui.main_window import MainWindow
    from canalyze.ui.startup_dialog import StartupDialog


def main() -> int:
    if not HAS_PYSIDE6:
        print(
            "PySide6 is not installed. Install project dependencies before launching the desktop application.",
            file=sys.stderr,
        )
        return 1

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
