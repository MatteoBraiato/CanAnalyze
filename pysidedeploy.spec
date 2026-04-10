[app]
title = CanAnalyze
project_dir = .
input_file = src/canalyze/app.py
project_file = canalyze.pyproject
exec_directory = dist
icon =

[python]
python_path = .venv-win\Scripts\python.exe
packages = nuitka,ordered-set,zstandard

[qt]
modules = Core,Gui,Widgets
qml_files = 
excluded_qml_plugins = 
plugins =

[nuitka]
mode = standalone
extra_args = --output-filename=CanAnalyze.exe --windows-console-mode=disable
onefile = False

