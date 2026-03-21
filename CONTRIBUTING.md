# Contributing to ComfyUI Auto-Installer

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone and install in development mode
git clone https://github.com/UmeAiRT/ComfyUI-Auto_installer.git
cd ComfyUI-Auto_installer
pip install -e ".[dev]"
```

## Running Tests

```bash
# All tests
uv run pytest tests/ -q

# With coverage
uv run coverage run --source=src -m pytest tests/ -q
uv run coverage report -m --skip-covered
```

## Code Style

- **Linter**: [Ruff](https://docs.astral.sh/ruff/)
- **Formatter**: Ruff format
- **Type hints**: Use them everywhere. `from __future__ import annotations` at the top.
- **Docstrings**: Google style, rst cross-references for classes/functions.
- **Enums**: Use `InstallType`, `NodeTier` from `src.enums` — no magic strings.
- **Errors**: Use `InstallerFatalError` — never bare `SystemExit(1)`.

Run lint before committing:

```bash
ruff check src/ tests/ --config pyproject.toml
```

## Architecture Overview

```
src/
├── cli.py              # Typer CLI entry point
├── enums.py            # InstallType, NodeTier, InstallerFatalError
├── config.py           # Pydantic models for dependencies.json
├── installer/          # 12-step installation orchestrator
│   ├── install.py      # Main orchestrator
│   ├── system.py       # Git, aria2 installation
│   ├── environment.py  # venv / conda creation
│   ├── dependencies.py # torch, wheels, packages
│   ├── nodes.py        # Custom nodes manifest
│   └── finalize.py     # Launchers, settings, model downloads
├── downloader/         # Model download engine
├── platform/           # OS abstraction (Windows, Linux)
└── utils/              # Logging, prompts, download, packaging
```

## Supply Chain Security

All external binaries and wheels are mirrored on our HuggingFace Assets repo with SHA-256 verification. When updating a binary:

1. Upload the new file to both HF and ModelScope repos
2. Compute `sha256sum` of the file
3. Update `scripts/dependencies.json` with new URL and hash
4. Update `tools_manifest.json` in the Assets repo

## Pull Request Guidelines

1. Branch from `python-rewrite` (current development branch)
2. Write tests for new functionality
3. Ensure `ruff check` passes and tests are green
4. Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`
