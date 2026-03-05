# Installation Guide

How to install taskfile on different platforms.

## Requirements

- Python 3.10 or higher
- pip (Python package installer)

## Quick Install

### Via pip (Recommended)

```bash
pip install taskfile
```

### With Optional Dependencies

For SSH remote execution:
```bash
pip install taskfile[paramiko]
```

For development:
```bash
pip install taskfile[dev]
```

All extras:
```bash
pip install taskfile[all]
```

## Platform-Specific Instructions

### macOS

```bash
# Using pip (recommended)
pip3 install taskfile

# Or with Homebrew (when available)
brew install taskfile
```

### Linux

```bash
# Debian/Ubuntu
sudo apt-get install python3-pip
pip3 install taskfile

# Fedora/RHEL
sudo dnf install python3-pip
pip3 install taskfile

# Arch Linux
sudo pacman -S python-pip
pip install taskfile
```

### Windows

```powershell
# Using pip
pip install taskfile

# Or with PowerShell (when available)
# Install-Module -Name Taskfile
```

## Development Install

Install from source for development:

```bash
# Clone repository
git clone https://github.com/tom-sapletta/taskfile.git
cd taskfile

# Create virtual environment
python -m venv venv

# Activate
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install in editable mode
pip install -e ".[dev]"

# Verify installation
taskfile --version
```

## Shell Completion

### Bash

Add to `~/.bashrc`:
```bash
eval "$(taskfile --completion bash)"
```

### Zsh

Add to `~/.zshrc`:
```zsh
eval "$(taskfile --completion zsh)"
```

### Fish

```fish
taskfile --completion fish > ~/.config/fish/completions/taskfile.fish
```

## Verification

Check installation:

```bash
taskfile --version
taskfile --help
taskfile doctor
```

## Upgrade

```bash
pip install --upgrade taskfile
```

## Uninstall

```bash
pip uninstall taskfile
```

Remove configuration:
```bash
rm -rf ~/.cache/taskfile
rm -rf ~/.taskfile
```

## Troubleshooting

### Permission Denied

```bash
# Use --user flag
pip install --user taskfile

# Or use virtual environment
python -m venv ~/venvs/taskfile
source ~/venvs/taskfile/bin/activate
pip install taskfile
```

### Python Not Found

```bash
# macOS
brew install python

# Ubuntu/Debian
sudo apt-get install python3 python3-pip

# Verify
python3 --version
pip3 --version
```

### Old Python Version

Taskfile requires Python 3.10+. Check your version:

```bash
python --version  # or python3 --version
```

Upgrade if needed:
- **macOS**: `brew install python@3.11`
- **Ubuntu**: `sudo apt-get install python3.11`
- **Windows**: Download from [python.org](https://python.org)

## Docker Install

Run without installing:

```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -v ~/.ssh:/root/.ssh \
  ghcr.io/tom-sapletta/taskfile:latest \
  taskfile --help
```

## Next Steps

1. Read the [Quick Start Guide](USAGE.md)
2. Create your first Taskfile: `taskfile init`
3. Explore [Examples](../examples/)

---

Last updated: 2024-03-05
