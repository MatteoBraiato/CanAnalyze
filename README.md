# CAN Log Analyzer

Desktop application for offline CAN log inspection, DBC-based decoding, and signal plotting.

## Dependency Management

This project uses `pyproject.toml` as the single source of truth for runtime and development dependencies.
Windows is the primary runtime target.

Use separate virtual environments per OS:

- `.venv-win` for launching and debugging the GUI on Windows
- `.venv-wsl` for optional WSL development and test runs

The checked-in `requirements-wsl.lock` captures a known working WSL environment. Do not reuse one virtual environment across Windows and WSL.

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
