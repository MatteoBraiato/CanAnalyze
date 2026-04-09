# CAN Log Analyzer

Desktop application for offline CAN log inspection, DBC-based decoding, and signal plotting.

Current capabilities:

- load `.asc` and `.trc` CAN logs
- optionally load a `.dbc` for message and signal decoding
- inspect raw frames and decoded message names in the message table
- select decoded signals from the `Messages / Signals` tree and plot them over time
- overlay signals with separate Y-axes when their engineering units differ
- expand or collapse the full message tree with one click
- switch between light and dark theme during the current session
- show the application version in the main window title and status area

## Dependency Management

This project uses `pyproject.toml` as the single source of truth for runtime and development dependencies.
Windows is the primary runtime target.

Use separate virtual environments per OS:

- `.venv-win` for launching and debugging the GUI on Windows
- `.venv-wsl` for optional WSL development and test runs

The checked-in `requirements-wsl.lock` captures a known working WSL environment. Do not reuse one virtual environment across Windows and WSL.

The application version is defined in `pyproject.toml` and exposed at runtime through package metadata. The installed app shows that version in the main window title so you can identify which build a user has installed.

## Windows Setup

Create the Windows environment from PowerShell:

```powershell
py -3.12 -m venv .venv-win
.venv-win\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.venv-win\Scripts\python.exe -m pip install -e .[dev]
```

Or use the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
```

Run the desktop application on Windows with:

```powershell
.venv-win\Scripts\python.exe -m canalyze
```

Or:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_windows.ps1
```

## Windows Packaging

For distribution to end users, build a normal Windows installer rather than shipping a raw Python environment.

Maintainer workflow:

1. Prepare the Windows virtual environment.
2. Build the standalone application bundle.
3. Build the installer.

Bundle build:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_bundle.ps1
```

Installer build:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1
```

Packaging notes:

- the bundle is generated with `pyside6-deploy` using `pysidedeploy.spec`
- the installer is generated with Inno Setup using `installer/CanAnalyze.iss`
- installer output is written to `release/`
- the installer filename includes the app version
- the installed app shows the same version in its window title

Prerequisites for packaging on Windows:

- `.venv-win` created with `scripts/setup_windows.ps1`
- Inno Setup 6 installed on the packaging machine

## WSL Setup

Create an isolated virtual environment in the project root and install the project in editable mode:

```bash
python3 -m venv .venv-wsl
. .venv-wsl/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

To recreate the currently verified WSL environment exactly, use:

```bash
python -m pip install -r requirements-wsl.lock
```

## Development

Run tests from WSL with:

```bash
python -m unittest discover -s tests
```

GUI execution from WSL is best-effort only. For the primary desktop workflow, run the application from Windows.

## Launching

Windows:

```powershell
.venv-win\Scripts\python.exe -m canalyze
```

WSL:

```bash
. .venv-wsl/bin/activate
python -m canalyze
```

## Using the UI

Typical workflow:

1. Start the application.
2. Select a CAN log file.
3. Optionally select a DBC file.
4. Load the files and wait for decoding to complete.
5. Browse decoded messages and signals in the left tree.
6. Check one or more signals to draw them in the plot.

Toolbar actions:

- `Open Log`: load a new `.asc` or `.trc` file
- `Load DBC`: attach or replace a DBC file
- `Unload DBC`: return to raw-frame mode
- `Expand All` / `Collapse All`: control the full message tree
- `Dark Theme` / `Light Theme`: toggle the session theme

Notes:

- signals with the same unit share one axis
- signals with different units render on separate synchronized Y-axes
- the selected theme is session-only and resets on the next launch
- the app version is visible in the main window title

## Testing

Run the full suite with:

```bash
. .venv-wsl/bin/activate
python -m unittest discover -s tests
```
