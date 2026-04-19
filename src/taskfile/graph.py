"""Task graph visualization for taskfile - show task dependencies."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig

console = Console()


def build_dependency_graph(config: TaskfileConfig) -> dict[str, list[str]]:
    """Build a dependency graph from task configuration.

    Returns dict mapping task names to their dependencies.
    """
    graph = {}

    for name, task in config.tasks.items():
        deps = list(task.deps) if task.deps else []
        graph[name] = deps

    return graph


def detect_cycles(graph: dict[str, list[str]]) -> list[str] | None:
    """Detect cycles in dependency graph.

    Returns None if no cycles, or a list representing a cycle if found.
    """
    visited = set()
    rec_stack = set()

    def visit(node: str, path: list[str]) -> list[str] | None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for dep in graph.get(node, []):
            if dep not in visited:
                result = visit(dep, path)
                if result:
                    return result
            elif dep in rec_stack:
                # Found cycle
                cycle_start = path.index(dep)
                return path[cycle_start:] + [dep]

        path.pop()
        rec_stack.remove(node)
        return None

    for node in graph:
        if node not in visited:
            cycle = visit(node, [])
            if cycle:
                return cycle

    return None


def print_task_tree(config: TaskfileConfig, root_task: str | None = None) -> None:
    """Print task dependencies as a tree.

    Args:
        config: Taskfile configuration
        root_task: If specified, show only this task and its dependencies
    """
    graph = build_dependency_graph(config)

    # Check for cycles
    cycle = detect_cycles(graph)
    if cycle:
        console.print(
            Panel(f"[bold red]⚠ Cycle detected:[/] {' → '.join(cycle)}", border_style="red")
        )
        return

    if root_task:
        if root_task not in config.tasks:
            console.print(f"[red]Task '{root_task}' not found[/]")
            return

        tree = Tree(f"[bold]{root_task}[/]")
        _add_deps_to_tree(tree, root_task, graph, config, set())
        console.print(tree)
    else:
        # Show all tasks
        # Find root tasks (those with no dependents)
        all_deps = set()
        for deps in graph.values():
            all_deps.update(deps)

        roots = [name for name in config.tasks.keys() if name not in all_deps]

        if not roots:
            # No clear roots, show all
            roots = list(config.tasks.keys())

        console.print("\n[bold]Task Dependency Tree:[/]")

        for root in sorted(roots):
            tree = Tree(f"[bold]{root}[/] [dim]{config.tasks[root].description or ''}[/]")
            _add_deps_to_tree(tree, root, graph, config, {root})
            console.print(tree)
            console.print()


def _add_deps_to_tree(
    tree: Tree,
    task_name: str,
    graph: dict[str, list[str]],
    config: TaskfileConfig,
    visited: set[str],
) -> None:
    """Recursively add dependencies to tree."""
    deps = graph.get(task_name, [])

    for dep in deps:
        if dep in visited:
            # Circular reference (shouldn't happen if cycle detection works)
            tree.add(f"[red]{dep} (circular)[/]")
            continue

        task = config.tasks.get(dep)
        if task:
            desc = task.description or ""
            if len(desc) > 40:
                desc = desc[:37] + "..."
            label = f"[dim]{dep}[/]"
            if desc:
                label += f" [dim]— {desc}[/]"

            branch = tree.add(label)

            if dep in graph and graph[dep]:
                _add_deps_to_tree(branch, dep, graph, config, visited | {dep})


def print_dependency_list(config: TaskfileConfig) -> None:
    """Print a flat list of tasks with their dependencies."""
    graph = build_dependency_graph(config)

    console.print("\n[bold]Task Dependencies:[/]\n")

    for name in sorted(config.tasks.keys()):
        task = config.tasks[name]
        deps = graph.get(name, [])

        if deps:
            deps_str = ", ".join(deps)
        else:
            deps_str = "(none)"

        console.print(f"[bold]{name}[/]")
        if task.description:
            console.print(f"  [dim]{task.description}[/]")
        console.print(f"  [dim]Dependencies:[/] {deps_str}")
        console.print()


def export_to_dot(config: TaskfileConfig, output_path: Path | None = None) -> str:
    """Export dependency graph to DOT format for Graphviz.

    Args:
        config: Taskfile configuration
        output_path: If specified, write to file

    Returns:
        DOT format string
    """
    graph = build_dependency_graph(config)

    lines = [
        "digraph taskfile {",
        "    rankdir=TB;",
        "    node [shape=box, style=rounded];",
        "",
    ]

    # Add nodes
    for name, task in config.tasks.items():
        label = name
        if task.description:
            # Escape quotes in description
            desc = task.description.replace('"', '\\"')
            label += f"\\n{desc}"
        lines.append(f'    "{name}" [label="{label}"];')

    lines.append("")

    # Add edges
    for name, deps in graph.items():
        for dep in deps:
            lines.append(f'    "{name}" -> "{dep}";')

    lines.append("}")

    dot_content = "\n".join(lines)

    if output_path:
        output_path.write_text(dot_content)

    return dot_content
