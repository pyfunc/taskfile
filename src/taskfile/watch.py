"""Watch mode for taskfile - auto-run tasks on file changes."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from rich.console import Console
from rich.panel import Panel

console = Console()

if TYPE_CHECKING:
    pass


class FileWatcher:
    """Watch files for changes and trigger callbacks."""

    def __init__(
        self,
        paths: list[str | Path],
        callback: Callable[[str], None],
        ignore_patterns: list[str] | None = None,
        debounce_ms: int = 300,
    ):
        self.paths = [Path(p).resolve() for p in paths]
        self.callback = callback
        self.ignore_patterns = ignore_patterns or [
            "*.pyc",
            "__pycache__",
            ".git",
            ".venv",
            "node_modules",
            ".pytest_cache",
            "*.egg-info",
            "dist",
            "build",
            ".aider*",
            "*.log",
            ".env*",
            ".DS_Store",
        ]
        self.debounce_ms = debounce_ms
        self._last_run = 0
        self._file_states: dict[Path, float] = {}
        self._running = False

    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored."""
        path_str = str(path)
        name = path.name

        for pattern in self.ignore_patterns:
            if pattern in path_str:
                return True
            if pattern.startswith("*") and name.endswith(pattern[1:]):
                return True
            if pattern.endswith("*") and name.startswith(pattern[:-1]):
                return True
            if name == pattern:
                return True

        return False

    def _get_files(self) -> dict[Path, float]:
        """Get all files with their modification times."""
        files = {}

        for watch_path in self.paths:
            if watch_path.is_file():
                if not self._should_ignore(watch_path):
                    files[watch_path] = watch_path.stat().st_mtime
            elif watch_path.is_dir():
                try:
                    for item in watch_path.rglob("*"):
                        if item.is_file() and not self._should_ignore(item):
                            try:
                                files[item] = item.stat().st_mtime
                            except (OSError, PermissionError):
                                pass
                except (OSError, PermissionError):
                    pass

        return files

    def _detect_changes(self) -> list[Path]:
        """Detect changed files since last check."""
        current_files = self._get_files()
        changes = []

        # Check for modified files
        for path, mtime in current_files.items():
            if path not in self._file_states:
                changes.append(path)
            elif self._file_states[path] != mtime:
                changes.append(path)

        # Check for deleted files
        for path in self._file_states:
            if path not in current_files:
                changes.append(path)

        self._file_states = current_files
        return changes

    def start(self) -> None:
        """Start watching files."""
        self._running = True
        self._file_states = self._get_files()

        console.print(
            Panel.fit(
                f"[bold green]👁️  Watch mode started[/]\n"
                f"[dim]Watching {len(self.paths)} path(s)[/]\n"
                f"[dim]Press Ctrl+C to stop[/]",
                border_style="green",
            )
        )

        try:
            while self._running:
                changes = self._detect_changes()

                if changes:
                    now = time.time() * 1000
                    if now - self._last_run > self.debounce_ms:
                        # Get the first changed file for display
                        change_str = str(changes[0].relative_to(Path.cwd()))
                        if len(changes) > 1:
                            change_str += f" (+{len(changes) - 1} more)"

                        self.callback(change_str)
                        self._last_run = now

                time.sleep(0.5)

        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop watching files."""
        self._running = False
        console.print("\n[dim]👁️  Watch mode stopped[/]")


def watch_tasks(
    task_names: list[str],
    watch_paths: list[str] | None = None,
    runner=None,
    debounce_ms: int = 300,
) -> None:
    """Watch files and run tasks on changes.

    Args:
        task_names: Tasks to run when files change
        watch_paths: Paths to watch (default: current directory)
        runner: TaskfileRunner instance
        debounce_ms: Debounce time in milliseconds
    """
    if watch_paths is None:
        watch_paths = ["."]

    def on_change(changed_file: str) -> None:
        """Callback when files change."""
        console.print(f"\n[bold yellow]🔄 File changed:[/] {changed_file}")
        console.print(f"[dim]Running: {' '.join(task_names)}[/]\n")

        try:
            success = runner.run(task_names)
            if success:
                console.print("\n[green]✓ Tasks completed successfully[/]")
            else:
                console.print("\n[red]✗ Tasks failed[/]")
        except Exception as e:
            console.print(f"\n[red]✗ Error: {e}[/]")

        console.print("\n[dim]Watching for changes... (Ctrl+C to stop)[/]")

    watcher = FileWatcher(
        paths=watch_paths,
        callback=on_change,
        debounce_ms=debounce_ms,
    )

    # Run once at start
    console.print("[dim]Running initial build...[/]")
    on_change("(initial run)")

    # Then watch for changes
    watcher.start()
