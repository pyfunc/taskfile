"""Remote task registry - download and share tasks like npm packages."""

from __future__ import annotations

import json
import os
import tarfile
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    pass


# Default registry URL (can be overridden by env var)
DEFAULT_REGISTRY = os.environ.get("TASKFILE_REGISTRY", "https://registry.taskfile.dev")
REGISTRY_DIR = Path.home() / ".taskfile" / "registry"


class TaskPackage:
    """Represents a task package in the registry."""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str = "",
        author: str = "",
        tags: list[str] | None = None,
        dependencies: list[str] | None = None,
        tasks: dict[str, Any] | None = None,
        url: str = "",
    ):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.tags = tags or []
        self.dependencies = dependencies or []
        self.tasks = tasks or {}
        self.url = url
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "tasks": self.tasks,
        }
    
    @classmethod
    def from_dict(cls, data: dict, url: str = "") -> TaskPackage:
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            tags=data.get("tags", []),
            dependencies=data.get("dependencies", []),
            tasks=data.get("tasks", {}),
            url=url,
        )


class RegistryClient:
    """Client for interacting with the task registry."""
    
    def __init__(self, registry_url: str | None = None):
        self.registry_url = registry_url or DEFAULT_REGISTRY
        self.cache_dir = REGISTRY_DIR / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def search(self, query: str, limit: int = 20) -> list[TaskPackage]:
        """Search for packages in the registry.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching packages
        """
        # For now, search local cache and known sources
        # In production, this would query a remote registry API
        
        results = []
        
        # Search GitHub topics
        try:
            github_results = self._search_github(query, limit)
            results.extend(github_results)
        except Exception:
            pass
        
        return results
    
    def _search_github(self, query: str, limit: int) -> list[TaskPackage]:
        """Search GitHub for taskfile repositories."""
        import urllib.request
        import json
        
        # Search for repos with taskfile topic
        search_url = f"https://api.github.com/search/repositories?q={query}+topic:taskfile+in:name,description&sort=stars&order=desc&per_page={limit}"
        
        req = urllib.request.Request(
            search_url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "taskfile-cli"
            }
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
        packages = []
        for item in data.get("items", []):
            pkg = TaskPackage(
                name=item["full_name"],
                version="1.0.0",
                description=item.get("description", ""),
                author=item["owner"]["login"],
                url=item["html_url"],
            )
            packages.append(pkg)
        
        return packages
    
    def install(
        self,
        package_name: str,
        version: str | None = None,
        save: bool = True,
    ) -> Path:
        """Install a package from the registry.
        
        Args:
            package_name: Package name (e.g., "tom-sapletta/web-tasks")
            version: Specific version to install (default: latest)
            save: Add to taskfile.json dependencies
            
        Returns:
            Path to installed package
        """
        # Parse package name (can be: user/repo, github:user/repo, or URL)
        source, name = self._parse_package_name(package_name)
        
        if source == "github":
            return self._install_from_github(name, version, save)
        elif source == "url":
            return self._install_from_url(package_name, version, save)
        else:
            raise ValueError(f"Unknown package source: {source}")
    
    def _parse_package_name(self, name: str) -> tuple[str, str]:
        """Parse package name and return (source, name).
        
        Examples:
            "tom-sapletta/web-tasks" -> ("github", "tom-sapletta/web-tasks")
            "github:tom-sapletta/web-tasks" -> ("github", "tom-sapletta/web-tasks")
            "https://github.com/..." -> ("url", "https://github.com/...")
        """
        if name.startswith("github:"):
            return "github", name[7:]
        elif name.startswith("http://") or name.startswith("https://"):
            return "url", name
        elif "/" in name:
            # Assume GitHub shorthand
            return "github", name
        else:
            return "unknown", name
    
    def _install_from_github(
        self,
        repo: str,
        version: str | None,
        save: bool,
    ) -> Path:
        """Install package from GitHub repository."""
        # Download repo as tarball
        if version:
            url = f"https://github.com/{repo}/archive/refs/tags/{version}.tar.gz"
        else:
            url = f"https://github.com/{repo}/archive/refs/heads/main.tar.gz"
        
        # Create package directory
        pkg_dir = REGISTRY_DIR / "packages" / repo.replace("/", "-")
        pkg_dir.mkdir(parents=True, exist_ok=True)
        
        # Download
        tarball_path = self.cache_dir / f"{repo.replace('/', '-')}.tar.gz"
        
        try:
            urllib.request.urlretrieve(url, tarball_path)
        except Exception as e:
            raise ValueError(f"Failed to download {repo}: {e}")
        
        # Extract
        with tarfile.open(tarball_path, "r:gz") as tar:
            # Extract to temp dir first
            temp_dir = pkg_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            tar.extractall(temp_dir)
            
            # Move contents up (remove nested dir)
            nested = list(temp_dir.iterdir())
            if len(nested) == 1 and nested[0].is_dir():
                for item in nested[0].iterdir():
                    dest = pkg_dir / item.name
                    if dest.exists():
                        import shutil
                        shutil.rmtree(dest, ignore_errors=True)
                    item.rename(dest)
                
                # Clean up
                nested[0].rmdir()
                temp_dir.rmdir()
        
        # Save to dependencies if requested
        if save:
            self._save_dependency(repo, version or "latest")
        
        return pkg_dir
    
    def _install_from_url(
        self,
        url: str,
        version: str | None,
        save: bool,
    ) -> Path:
        """Install package from direct URL."""
        # Parse URL to get package name
        parsed = urlparse(url)
        pkg_name = Path(parsed.path).stem
        
        pkg_dir = REGISTRY_DIR / "packages" / pkg_name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        
        # Download
        if url.endswith(".tar.gz") or url.endswith(".tgz"):
            tarball_path = self.cache_dir / f"{pkg_name}.tar.gz"
            urllib.request.urlretrieve(url, tarball_path)
            
            with tarfile.open(tarball_path, "r:gz") as tar:
                tar.extractall(pkg_dir)
        else:
            # Assume single Taskfile.yml
            taskfile_path = pkg_dir / "Taskfile.yml"
            urllib.request.urlretrieve(url, taskfile_path)
        
        if save:
            self._save_dependency(url, version or "latest")
        
        return pkg_dir
    
    def _save_dependency(self, name: str, version: str) -> None:
        """Save dependency to taskfile.json."""
        deps_file = Path("taskfile.json")
        
        deps = {}
        if deps_file.exists():
            deps = json.loads(deps_file.read_text())
        
        deps[name] = version
        deps_file.write_text(json.dumps(deps, indent=2))
    
    def list_installed(self) -> list[tuple[str, Path]]:
        """List all installed packages."""
        packages_dir = REGISTRY_DIR / "packages"
        
        if not packages_dir.exists():
            return []
        
        installed = []
        for pkg_dir in packages_dir.iterdir():
            if pkg_dir.is_dir():
                # Read package info if available
                info_file = pkg_dir / "package.json"
                if info_file.exists():
                    info = json.loads(info_file.read_text())
                    name = info.get("name", pkg_dir.name)
                else:
                    name = pkg_dir.name
                
                installed.append((name, pkg_dir))
        
        return installed
    
    def uninstall(self, package_name: str) -> bool:
        """Uninstall a package."""
        pkg_dir = REGISTRY_DIR / "packages" / package_name.replace("/", "-")
        
        if not pkg_dir.exists():
            return False
        
        import shutil
        shutil.rmtree(pkg_dir)
        
        # Remove from dependencies
        deps_file = Path("taskfile.json")
        if deps_file.exists():
            deps = json.loads(deps_file.read_text())
            if package_name in deps:
                del deps[package_name]
                deps_file.write_text(json.dumps(deps, indent=2))
        
        return True


def include_installed_tasks(taskfile_config: dict) -> dict:
    """Include tasks from installed packages into taskfile config.
    
    This function merges tasks from installed packages into the main
    taskfile configuration.
    """
    registry_client = RegistryClient()
    installed = registry_client.list_installed()
    
    for name, pkg_dir in installed:
        # Look for Taskfile.yml in package directory
        taskfile_path = pkg_dir / "Taskfile.yml"
        if taskfile_path.exists():
            try:
                import yaml
                with open(taskfile_path) as f:
                    pkg_config = yaml.safe_load(f)
                
                # Merge tasks with namespace prefix
                if "tasks" in pkg_config:
                    for task_name, task_def in pkg_config["tasks"].items():
                        namespaced_name = f"{name}:{task_name}"
                        taskfile_config["tasks"][namespaced_name] = task_def
                        
                        # Update description to indicate source
                        if "desc" in task_def:
                            task_def["desc"] = f"[{name}] {task_def['desc']}"
                        
            except Exception:
                # Skip packages that can't be loaded
                pass
    
    return taskfile_config
