"""Cache and incremental builds for taskfile.

Tracks file hashes and task outputs to avoid re-running unchanged tasks.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from taskfile.models import Task


class TaskCache:
    """Manages caching of task outputs based on input file hashes."""
    
    CACHE_DIR = Path.home() / ".cache" / "taskfile"
    
    def __init__(self, project_hash: str):
        self.project_hash = project_hash
        self.cache_file = self.CACHE_DIR / f"{project_hash}.json"
        self._cache: dict[str, Any] = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                self._cache = json.loads(self.cache_file.read_text())
            except (json.JSONDecodeError, IOError):
                self._cache = {}
        else:
            self._cache = {}
    
    def _save_cache(self) -> None:
        """Save cache to disk."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(self._cache, indent=2))
    
    def _compute_file_hash(self, file_path: Path) -> str | None:
        """Compute MD5 hash of a file."""
        try:
            content = file_path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except (IOError, OSError):
            return None
    
    def _compute_task_hash(self, task: Task, env_vars: dict[str, str]) -> str:
        """Compute a hash representing task inputs."""
        # Hash of: task commands + env vars + task description
        hasher = hashlib.md5()
        
        # Hash commands
        for cmd in task.commands:
            hasher.update(cmd.encode())
        
        # Hash relevant env vars (sorted for consistency)
        for key in sorted(env_vars.keys()):
            hasher.update(f"{key}={env_vars[key]}".encode())
        
        # Hash working directory
        if task.working_dir:
            hasher.update(task.working_dir.encode())
        
        return hasher.hexdigest()
    
    def _get_input_files_hash(self, patterns: list[str]) -> str | None:
        """Compute hash of input files matching patterns."""
        import fnmatch
        
        all_hashes = []
        
        for pattern in patterns:
            # Handle glob patterns
            if '*' in pattern or '?' in pattern:
                base_dir = Path('.')
                for path in base_dir.rglob(pattern):
                    if path.is_file():
                        file_hash = self._compute_file_hash(path)
                        if file_hash:
                            all_hashes.append(f"{path}:{file_hash}")
            else:
                # Direct file or directory
                path = Path(pattern)
                if path.is_file():
                    file_hash = self._compute_file_hash(path)
                    if file_hash:
                        all_hashes.append(f"{path}:{file_hash}")
                elif path.is_dir():
                    for file_path in path.rglob('*'):
                        if file_path.is_file():
                            file_hash = self._compute_file_hash(file_path)
                            if file_hash:
                                all_hashes.append(f"{file_path}:{file_hash}")
        
        if not all_hashes:
            return None
        
        # Sort and hash all file hashes together
        all_hashes.sort()
        return hashlib.md5(''.join(all_hashes).encode()).hexdigest()
    
    def is_fresh(
        self,
        task: Task,
        task_name: str,
        env_vars: dict[str, str],
        input_patterns: list[str] | None = None,
    ) -> tuple[bool, str | None]:
        """Check if cached result is still valid.
        
        Returns:
            (is_fresh, output) - is_fresh is True if cache hit, output is cached output
        """
        task_hash = self._compute_task_hash(task, env_vars)
        
        # Get input files hash if patterns provided
        input_hash = None
        if input_patterns:
            input_hash = self._get_input_files_hash(input_patterns)
        
        cache_key = f"{task_name}:{task_hash}"
        
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            
            # Check if input files changed
            if input_patterns and input_hash:
                cached_input_hash = entry.get('input_hash')
                if cached_input_hash != input_hash:
                    return False, None  # Input files changed
            
            # Check if output files still exist
            output_files = entry.get('output_files', [])
            if output_files:
                all_exist = all(Path(f).exists() for f in output_files)
                if not all_exist:
                    return False, None  # Output files missing
            
            # Cache hit!
            return True, entry.get('output')
        
        return False, None
    
    def save(
        self,
        task: Task,
        task_name: str,
        env_vars: dict[str, str],
        output: str,
        input_patterns: list[str] | None = None,
        output_files: list[str] | None = None,
    ) -> None:
        """Save task result to cache."""
        task_hash = self._compute_task_hash(task, env_vars)
        input_hash = None
        
        if input_patterns:
            input_hash = self._get_input_files_hash(input_patterns)
        
        cache_key = f"{task_name}:{task_hash}"
        
        self._cache[cache_key] = {
            'timestamp': time.time(),
            'output': output,
            'input_hash': input_hash,
            'output_files': output_files or [],
        }
        
        self._save_cache()
    
    def clear(self, task_name: str | None = None) -> int:
        """Clear cache entries.
        
        Args:
            task_name: Clear only entries for this task, or all if None
            
        Returns:
            Number of entries cleared
        """
        if task_name is None:
            count = len(self._cache)
            self._cache = {}
            self._save_cache()
            return count
        else:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{task_name}:")]
            for key in keys_to_remove:
                del self._cache[key]
            self._save_cache()
            return len(keys_to_remove)
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self._cache)
        tasks = set(k.split(':')[0] for k in self._cache.keys())
        
        # Calculate total size
        total_size = 0
        for entry in self._cache.values():
            output = entry.get('output', '')
            total_size += len(output.encode())
        
        return {
            'total_entries': total_entries,
            'unique_tasks': len(tasks),
            'cache_file': str(self.cache_file),
            'total_size_bytes': total_size,
        }


def get_project_hash(taskfile_path: str | Path | None = None) -> str:
    """Get a unique hash for the current project.
    
    Used to namespace cache entries per project.
    """
    from taskfile.parser import find_taskfile
    
    try:
        if taskfile_path:
            path = Path(taskfile_path).resolve()
        else:
            path = find_taskfile().resolve()
    except Exception:
        # Fallback to current directory
        path = Path.cwd()
    
    # Use directory path as project identifier
    project_id = str(path.parent)
    return hashlib.md5(project_id.encode()).hexdigest()[:16]
