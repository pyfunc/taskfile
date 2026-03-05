# Contributing to Taskfile

Thank you for your interest in contributing to Taskfile! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.10+
- Git
- Virtual environment (venv or conda)

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/tom-sapletta/taskfile.git
cd taskfile

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Project Structure

```
taskfile/
├── src/
│   └── taskfile/
│       ├── cli/           # CLI commands
│       ├── cache.py       # Caching system
│       ├── converters.py  # Import/export
│       ├── graph.py       # Dependency graph
│       ├── models.py      # Data models
│       ├── notifications.py  # Desktop notifications
│       ├── parser.py      # YAML parsing
│       ├── registry.py    # Package registry
│       ├── runner.py      # Task execution
│       ├── scaffold.py    # Template generation
│       ├── ssh.py         # SSH client
│       ├── watch.py       # File watcher
│       └── webui.py       # Web dashboard
├── tests/                 # Test suite
├── docs/                  # Documentation
├── examples/              # Example projects
└── pyproject.toml         # Project config
```

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists
2. Create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, Python version, taskfile version)

### Suggesting Features

1. Open a discussion first for major features
2. Describe the use case
3. Explain why existing solutions don't work

### Pull Requests

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/my-feature`
3. **Make changes**
4. **Test**: Run `pytest` and ensure all tests pass
5. **Commit**: Use clear commit messages
6. **Push**: `git push origin feature/my-feature`
7. **Open PR**: Link to any related issues

## Code Standards

### Python Style

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use `black` for formatting: `black src/`
- Use `isort` for imports: `isort src/`

### Documentation

- Docstrings for all public functions
- Type hints for parameters and returns
- Update docs/ if adding features

### Testing

- Write tests for new features
- Aim for >80% coverage
- Use pytest fixtures
- Test edge cases

Example test:
```python
def test_runner_executes_commands():
    runner = TaskfileRunner(
        config=mock_config,
        env_name="local"
    )
    success = runner.run(["test-task"])
    assert success is True
```

## Areas for Contribution

### High Priority

- [ ] **Testing** — Increase test coverage
- [ ] **Documentation** — More examples and guides
- [ ] **Windows support** — Better Windows compatibility
- [ ] **Performance** — Optimize large project handling

### Medium Priority

- [ ] **IDE integrations** — VS Code extension
- [ ] **More converters** — Import from more formats
- [ ] **Plugins** — Plugin system architecture
- [ ] **Themes** — Web UI theming

### Documentation

- [ ] **Tutorials** — Video or written tutorials
- [ ] **Examples** — More real-world examples
- [ ] **Translations** — Translate docs to other languages

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Create git tag: `git tag v1.0.0`
5. Push tag: `git push origin v1.0.0`
6. GitHub Actions will publish to PyPI

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Assume good intentions

## Questions?

- Open a [Discussion](https://github.com/tom-sapletta/taskfile/discussions)
- Join our Discord (coming soon)
- Email: tom@sapletta.com

Thank you for contributing! 🎉
