# CLI Commands

All commands are available via the `umeairt-comfyui-installer` CLI.

## Synopsis

```bash
umeairt-comfyui-installer <command> [OPTIONS]
```

## Commands

### `install`

Full installation of ComfyUI with all dependencies.

```bash
umeairt-comfyui-installer install --path /path/to/install --type venv
```

| Option | Description | Default |
|--------|-------------|---------|
| `--path` | Installation directory | `.` |
| `--type` | Environment type: `venv` or `conda` | `venv` |
| `--verbose` / `-v` | Show detailed output | Off |
| `--skip-nodes` | Skip custom node installation | Off |
| `--gpu` | Manual GPU override (e.g. `cu130`, `directml`) | Auto-detect |

### `update`

Update ComfyUI core, all bundled custom nodes, and Python dependencies.

```bash
umeairt-comfyui-installer update --path /path/to/install
```

| Option | Description | Default |
|--------|-------------|---------|
| `--path` | Installation directory | `.` |
| `--verbose` / `-v` | Show detailed output | Off |
| `--nodes` / `-n` | Node bundle: `minimal`, `umeairt`, `full` | `full` |
| `--yes` / `-y` | Non-interactive mode | Off |

### `download-models`

Interactive model download menu with VRAM-based recommendations.

```bash
umeairt-comfyui-installer download-models --path /path/to/install
```

### `scan-models`

Scan model files for malicious pickle code using `picklescan`.

```bash
umeairt-comfyui-installer scan-models --path /path/to/install
```

### `info`

Display system information (GPU, Python version, installed tools).

```bash
umeairt-comfyui-installer info
```

### `version`

Show the installer version.

```bash
umeairt-comfyui-installer version
```

## Global Options

All commands support:

- `--path PATH` — Installation directory
- `--verbose` / `-v` — Enable detailed logging output
