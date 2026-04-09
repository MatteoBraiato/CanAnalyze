[app]
title = CanAnalyze
project_dir = .
input_file = src/canalyze/__main__.py
project_file = canalyze.pyproject
exec_directory = dist

[python]
python_path = .venv-win\Scripts\python.exe

[qt]
modules = Core,Gui,Widgets

[nuitka]
onefile = False
