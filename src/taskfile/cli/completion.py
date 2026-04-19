"""## Shell completion for taskfile

Auto-complete task names and CLI options for popular shells.

### Supported Shells

| Shell | Command | File |
|-------|---------|------|
| `bash` | `taskfile completion bash` | `~/.bashrc` |
| `zsh` | `taskfile completion zsh` | `~/.zshrc` |
| `fish` | `taskfile completion fish` | `~/.config/fish/completions/` |

### Setup

**Bash:**
```bash
eval "$(taskfile completion bash)"
```

**Zsh:**
```zsh
eval "$(taskfile completion zsh)"
```

**Fish:**
```fish
taskfile completion fish | source
```

### Why clickmd?

Uses `clickmd` for CLI framework compatibility. Note: Uses `click.shell_completion`
from the underlying click library for completion items.

### Dependencies

- `clickmd` - CLI framework (provides click underneath)
- `click.shell_completion` - Shell completion utilities
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.shell_completion import CompletionItem

from taskfile.parser import load_taskfile, TaskfileNotFoundError

if TYPE_CHECKING:
    pass


def get_task_names(ctx, param, incomplete: str) -> list[CompletionItem]:
    """Shell completion for task names."""
    try:
        taskfile_path = ctx.params.get("taskfile_path")
        if taskfile_path:
            config = load_taskfile(taskfile_path)
        else:
            try:
                config = load_taskfile()
            except TaskfileNotFoundError:
                return []

        # Filter tasks that match incomplete
        tasks = []
        for name in config.tasks.keys():
            if name.startswith(incomplete):
                task = config.tasks[name]
                desc = task.description or ""
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                tasks.append(CompletionItem(name, help=desc))

        return tasks
    except Exception:
        return []


def get_environment_names(ctx, param, incomplete: str) -> list[CompletionItem]:
    """Shell completion for environment names."""
    try:
        taskfile_path = ctx.params.get("taskfile_path")
        if taskfile_path:
            config = load_taskfile(taskfile_path)
        else:
            try:
                config = load_taskfile()
            except TaskfileNotFoundError:
                return []

        envs = []
        for name in config.environments.keys():
            if name.startswith(incomplete):
                env = config.environments[name]
                desc = f"{env.container_runtime or 'local'}"
                if env.ssh_host:
                    desc += f" → {env.ssh_host}"
                envs.append(CompletionItem(name, help=desc))

        return envs
    except Exception:
        return []


def get_platform_names(ctx, param, incomplete: str) -> list[CompletionItem]:
    """Shell completion for platform names."""
    try:
        taskfile_path = ctx.params.get("taskfile_path")
        if taskfile_path:
            config = load_taskfile(taskfile_path)
        else:
            try:
                config = load_taskfile()
            except TaskfileNotFoundError:
                return []

        platforms = []
        for name in config.platforms.keys():
            if name.startswith(incomplete):
                plat = config.platforms[name]
                desc = f"{len(plat.envs)} environments"
                platforms.append(CompletionItem(name, help=desc))

        return platforms
    except Exception:
        return []


def generate_completion_script(shell: str) -> str:
    """Generate shell completion script for taskfile.

    Supported shells: bash, zsh, fish
    """
    if shell == "bash":
        return """
_taskfile_completion() {
    local IFS=$'\n'
    local response

    response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD _TASKFILE_COMPLETE=bash_complete taskfile)

    for completion in $response; do
        IFS=',' read -r first rest <<< "$completion"
        if [[ "$rest" == "" ]]; then
            COMPREPLY+=("$first")
        else
            COMPREPLY+=("$first")
        fi
    done

    return 0
}

complete -F _taskfile_completion -o bashdefault -o default taskfile
""".strip()

    elif shell == "zsh":
        return """
#compdef taskfile

_taskfile_completion() {
    local -a completions
    local -a response
    
    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _TASKFILE_COMPLETE=zsh_complete taskfile)}")
    
    for line in $response; do
        IFS=',' read -r task desc <<< "$line"
        completions+=("${task}:${desc}")
    done
    
    _describe -V 'taskfile tasks' completions
}

compdef _taskfile_completion taskfile
""".strip()

    elif shell == "fish":
        return """
complete -c taskfile -f

function __taskfile_complete
    set -l response (env COMP_WORDS=(commandline -o) COMP_CWORD=(math (count (commandline -o)) - 1) _TASKFILE_COMPLETE=fish_complete taskfile)
    for line in $response
        echo $line
    end
end

complete -c taskfile -a '(__taskfile_complete)'
""".strip()

    else:
        raise ValueError(f"Unsupported shell: {shell}")
