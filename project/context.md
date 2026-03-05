# System Architecture Analysis

## Overview

- **Project**: /home/tom/github/pyfunc/taskfile
- **Analysis Mode**: static
- **Total Functions**: 104
- **Total Classes**: 21
- **Modules**: 26
- **Entry Points**: 65

## Architecture by Module

### src.taskfile.quadlet
- **Functions**: 17
- **File**: `quadlet.py`

### src.taskfile.runner
- **Functions**: 11
- **Classes**: 2
- **File**: `runner.py`

### src.taskfile.cigen.base
- **Functions**: 9
- **Classes**: 1
- **File**: `base.py`

### src.taskfile.cirunner
- **Functions**: 8
- **Classes**: 3
- **File**: `cirunner.py`

### src.taskfile.compose
- **Functions**: 7
- **Classes**: 1
- **File**: `compose.py`

### src.taskfile.cli.main
- **Functions**: 7
- **File**: `main.py`

### src.taskfile.cli.quadlet
- **Functions**: 6
- **File**: `quadlet.py`

### src.taskfile.cli.ci
- **Functions**: 6
- **File**: `ci.py`

### src.taskfile.cli.deploy
- **Functions**: 6
- **File**: `deploy.py`

### src.taskfile.models
- **Functions**: 6
- **Classes**: 6
- **File**: `models.py`

### src.taskfile.cigen.github
- **Functions**: 4
- **Classes**: 1
- **File**: `github.py`

### src.taskfile.cigen
- **Functions**: 4
- **File**: `__init__.py`

### src.taskfile.parser
- **Functions**: 3
- **Classes**: 2
- **File**: `parser.py`

### src.taskfile.cigen.drone
- **Functions**: 2
- **Classes**: 1
- **File**: `drone.py`

### src.taskfile.cigen.gitlab
- **Functions**: 2
- **Classes**: 1
- **File**: `gitlab.py`

### src.taskfile.cigen.jenkins
- **Functions**: 2
- **Classes**: 1
- **File**: `jenkins.py`

### src.taskfile.cigen.gitea
- **Functions**: 2
- **Classes**: 1
- **File**: `gitea.py`

### src.taskfile.scaffold
- **Functions**: 1
- **File**: `__init__.py`

### src.taskfile.cigen.makefile
- **Functions**: 1
- **Classes**: 1
- **File**: `makefile.py`

## Key Entry Points

Main execution flows into the system:

### src.taskfile.models.TaskfileConfig.from_dict
> Parse raw YAML dict into TaskfileConfig.
- **Calls**: cls, data.get, isinstance, None.items, None.items, data.get, isinstance, config.pipeline.infer_from_tasks

### src.taskfile.cli.ci.ci_generate
> Generate CI/CD config files from Taskfile.yml pipeline section.


Examples:
    taskfile ci generate --target github
    taskfile ci generate --targe
- **Calls**: ci.command, click.option, click.option, click.option, src.taskfile.parser.load_taskfile, console.print, None.join, console.print

### src.taskfile.cirunner.PipelineRunner.run
> Run pipeline stages in order.

Args:
    stage_filter: Only run these stages (None = all non-manual)
    skip_stages: Skip these stages
    stop_at: S
- **Calls**: self._resolve_stages, self._print_pipeline_header, time.time, enumerate, self._print_summary, console.print, console.print, console.print

### src.taskfile.cli.deploy.deploy_cmd
> Full deploy pipeline: build → push → generate Quadlet → upload → restart.

Reads environment config from Taskfile.yml and performs the correct
deploy 
- **Calls**: main.command, click.option, opts.get, opts.get, opts.get, src.taskfile.parser.load_taskfile, env.resolve_variables, variables.update

### src.taskfile.runner.TaskfileRunner.run_task
> Run a task and its dependencies. Returns True on success.
- **Calls**: Text, header.append, console.print, time.time, console.print, self._executed.add, console.print, None.join

### src.taskfile.models.PipelineConfig.from_dict
- **Calls**: cls, data.get, isinstance, str, data.get, data.get, data.get, data.get

### src.taskfile.cli.quadlet.quadlet_generate
> Generate Quadlet .container files from docker-compose.yml.


Examples:
    taskfile quadlet generate
    taskfile quadlet generate --env-file .env.pr
- **Calls**: quadlet.command, click.option, click.option, click.option, click.option, click.option, click.option, opts.get

### src.taskfile.cigen.makefile.MakefileTarget.generate
- **Calls**: sorted, None.join, self.config.tasks.items, task_name.replace, lines.append, lines.append, lines.append, lines.append

### src.taskfile.cli.ci.ci_run
> Run CI/CD pipeline stages locally.

Runs the same pipeline that would run on GitHub/GitLab/etc,
but directly on your machine. No runner needed.


Exa
- **Calls**: ci.command, click.option, click.option, click.option, src.taskfile.parser.load_taskfile, PipelineRunner, runner.run, sys.exit

### src.taskfile.runner.TaskfileRunner.list_tasks
> Print available tasks and environments.
- **Calls**: console.print, sorted, console.print, sorted, console.print, self.config.tasks.items, console.print, self.config.environments.items

### src.taskfile.cli.main.info
> Show detailed info about a specific task.
- **Calls**: main.command, click.argument, src.taskfile.parser.load_taskfile, console.print, console.print, console.print, sys.exit, console.print

### src.taskfile.cli.quadlet.quadlet_upload
> Upload generated Quadlet files to remote server via SSH.

Uses environment settings from Taskfile.yml for SSH connection
and remote quadlet directory.
- **Calls**: quadlet.command, click.option, opts.get, opts.get, src.taskfile.parser.load_taskfile, src.taskfile.cli.quadlet._get_upload_env, src.taskfile.cli.quadlet._get_upload_files, src.taskfile.cli.quadlet._run_upload_commands

### src.taskfile.cli.main.init
> Create a new Taskfile.yml in the current directory.


Templates:
    minimal    — basic build/deploy tasks
    web        — web app with Docker + Tra
- **Calls**: main.command, click.option, click.option, Path, src.taskfile.scaffold.generate_taskfile, outpath.write_text, console.print, console.print

### src.taskfile.cli.main.validate
> Validate the Taskfile without running anything.
- **Calls**: main.command, src.taskfile.parser.load_taskfile, src.taskfile.parser.validate_taskfile, console.print, console.print, console.print, console.print, sys.exit

### src.taskfile.cli.ci.ci_preview
> Preview generated CI/CD config without writing files.


Examples:
    taskfile ci preview --target github
    taskfile ci preview --target gitlab
- **Calls**: ci.command, click.option, src.taskfile.parser.load_taskfile, src.taskfile.cigen.preview_ci, console.print, console.print, opts.get, console.print

### src.taskfile.compose.ComposeFile.__init__
- **Calls**: Path, self.variables.update, src.taskfile.compose.resolve_dict, Path, self.variables.update, self.compose_path.is_file, FileNotFoundError, open

### src.taskfile.cirunner.PipelineRunner._print_summary
> Print final pipeline results summary.
- **Calls**: console.print, Table, table.add_column, table.add_column, table.add_column, table.add_column, console.print, console.print

### src.taskfile.cli.main.main
> taskfile — Universal task runner with multi-environment deploy.


Run tasks:     taskfile run build deploy
List tasks:    taskfile list
Init project:
- **Calls**: click.group, click.version_option, click.option, click.option, click.option, click.option, click.option, ctx.ensure_object

### src.taskfile.compose.ComposeFile.get_traefik_labels
> Extract Traefik labels from a service.
- **Calls**: self.get_service, service.get, isinstance, isinstance, item.partition, result.items, k.startswith, labels.items

### src.taskfile.runner.TaskfileRunner.__init__
- **Calls**: set, self.env.resolve_variables, self.variables.update, self.variables.setdefault, self.variables.setdefault, self.variables.setdefault, src.taskfile.parser.load_taskfile, console.print

### src.taskfile.cirunner.PipelineRunner.list_stages
> Print available pipeline stages.
- **Calls**: console.print, enumerate, console.print, console.print, console.print, console.print, None.join, console.print

### src.taskfile.cli.main.run
> Run one or more tasks.


Examples:
    taskfile run build
    taskfile run build deploy --env prod
    taskfile run release --var TAG=v1.2.3
    task
- **Calls**: main.command, click.argument, TaskfileRunner, runner.run, sys.exit, list, console.print, sys.exit

### src.taskfile.runner.TaskfileRunner.run_command
> Execute a single command, locally or via SSH.
- **Calls**: self.expand_variables, self._is_remote_command, self._wrap_ssh, console.print, console.print, subprocess.run, console.print

### src.taskfile.cli.ci.ci_list
> List pipeline stages defined in Taskfile.yml.
- **Calls**: ci.command, src.taskfile.parser.load_taskfile, PipelineRunner, runner.list_stages, opts.get, console.print, sys.exit

### src.taskfile.runner.TaskfileRunner.expand_variables
> Replace {{VAR}} and ${VAR} placeholders with resolved values.
- **Calls**: self.variables.items, result.replace, result.replace, result.replace, isinstance, str

### src.taskfile.cli.ci.ci_targets
> List available CI/CD generation targets.
- **Calls**: ci.command, console.print, src.taskfile.cigen.list_targets, console.print, console.print, console.print

### src.taskfile.cli.main.list_tasks
> List available tasks and environments.
- **Calls**: main.command, src.taskfile.parser.load_taskfile, TaskfileRunner, runner.list_tasks, console.print, sys.exit

### src.taskfile.cigen.gitlab.GitLabCITarget.generate
- **Calls**: src.taskfile.cigen.base._yaml_dump, src.taskfile.cigen.base._sanitize_id, job.get, before.extend, self._stage_tasks_cmd, self._stage_tasks_cmd

### src.taskfile.cigen.github.GitHubActionsTarget._build_steps
- **Calls**: steps.append, steps.append, steps.append, steps.append, self._stage_tasks_cmd, None.join

### src.taskfile.models.PipelineConfig.infer_from_tasks
> Auto-generate pipeline stages from task 'stage' fields if no stages defined.
- **Calls**: tasks.items, stage_map.items, self.stages.append, None.append, PipelineStage, stage_map.setdefault

## Process Flows

Key execution flows identified:

### Flow 1: from_dict
```
from_dict [src.taskfile.models.TaskfileConfig]
```

### Flow 2: ci_generate
```
ci_generate [src.taskfile.cli.ci]
  └─ →> load_taskfile
      └─> find_taskfile
```

### Flow 3: run
```
run [src.taskfile.cirunner.PipelineRunner]
```

### Flow 4: deploy_cmd
```
deploy_cmd [src.taskfile.cli.deploy]
```

### Flow 5: run_task
```
run_task [src.taskfile.runner.TaskfileRunner]
```

### Flow 6: quadlet_generate
```
quadlet_generate [src.taskfile.cli.quadlet]
```

### Flow 7: generate
```
generate [src.taskfile.cigen.makefile.MakefileTarget]
```

### Flow 8: ci_run
```
ci_run [src.taskfile.cli.ci]
  └─ →> load_taskfile
      └─> find_taskfile
```

### Flow 9: list_tasks
```
list_tasks [src.taskfile.runner.TaskfileRunner]
```

### Flow 10: info
```
info [src.taskfile.cli.main]
  └─ →> load_taskfile
      └─> find_taskfile
```

## Key Classes

### src.taskfile.runner.TaskfileRunner
> Executes tasks from a Taskfile configuration.
- **Methods**: 10
- **Key Methods**: src.taskfile.runner.TaskfileRunner.__init__, src.taskfile.runner.TaskfileRunner.expand_variables, src.taskfile.runner.TaskfileRunner.run_command, src.taskfile.runner.TaskfileRunner._is_remote_command, src.taskfile.runner.TaskfileRunner._strip_remote_prefix, src.taskfile.runner.TaskfileRunner._wrap_ssh, src.taskfile.runner.TaskfileRunner.check_condition, src.taskfile.runner.TaskfileRunner.run_task, src.taskfile.runner.TaskfileRunner.run, src.taskfile.runner.TaskfileRunner.list_tasks

### src.taskfile.compose.ComposeFile
> Parsed docker-compose.yml with environment resolution.
- **Methods**: 7
- **Key Methods**: src.taskfile.compose.ComposeFile.__init__, src.taskfile.compose.ComposeFile.services, src.taskfile.compose.ComposeFile.networks, src.taskfile.compose.ComposeFile.volumes, src.taskfile.compose.ComposeFile.get_service, src.taskfile.compose.ComposeFile.get_traefik_labels, src.taskfile.compose.ComposeFile.service_names

### src.taskfile.cirunner.PipelineRunner
> Runs CI/CD pipeline stages locally using TaskfileRunner.

The pipeline is just an ordered list of st
- **Methods**: 6
- **Key Methods**: src.taskfile.cirunner.PipelineRunner.__init__, src.taskfile.cirunner.PipelineRunner.run, src.taskfile.cirunner.PipelineRunner._resolve_stages, src.taskfile.cirunner.PipelineRunner._print_pipeline_header, src.taskfile.cirunner.PipelineRunner._print_summary, src.taskfile.cirunner.PipelineRunner.list_stages

### src.taskfile.cigen.base.CITarget
> Base class for CI/CD target generators.
- **Methods**: 6
- **Key Methods**: src.taskfile.cigen.base.CITarget.__init__, src.taskfile.cigen.base.CITarget.generate, src.taskfile.cigen.base.CITarget.write, src.taskfile.cigen.base.CITarget._tag_var, src.taskfile.cigen.base.CITarget._stage_env_flag, src.taskfile.cigen.base.CITarget._stage_tasks_cmd

### src.taskfile.cigen.github.GitHubActionsTarget
- **Methods**: 4
- **Key Methods**: src.taskfile.cigen.github.GitHubActionsTarget._tag_var, src.taskfile.cigen.github.GitHubActionsTarget._build_steps, src.taskfile.cigen.github.GitHubActionsTarget._apply_conditions, src.taskfile.cigen.github.GitHubActionsTarget.generate
- **Inherits**: CITarget

### src.taskfile.models.Environment
> Deployment environment configuration.
- **Methods**: 4
- **Key Methods**: src.taskfile.models.Environment.ssh_target, src.taskfile.models.Environment.ssh_opts, src.taskfile.models.Environment.is_remote, src.taskfile.models.Environment.resolve_variables

### src.taskfile.cigen.drone.DroneCITarget
- **Methods**: 2
- **Key Methods**: src.taskfile.cigen.drone.DroneCITarget._tag_var, src.taskfile.cigen.drone.DroneCITarget.generate
- **Inherits**: CITarget

### src.taskfile.cigen.gitlab.GitLabCITarget
- **Methods**: 2
- **Key Methods**: src.taskfile.cigen.gitlab.GitLabCITarget._tag_var, src.taskfile.cigen.gitlab.GitLabCITarget.generate
- **Inherits**: CITarget

### src.taskfile.cigen.jenkins.JenkinsTarget
- **Methods**: 2
- **Key Methods**: src.taskfile.cigen.jenkins.JenkinsTarget._tag_var, src.taskfile.cigen.jenkins.JenkinsTarget.generate
- **Inherits**: CITarget

### src.taskfile.cigen.gitea.GiteaActionsTarget
- **Methods**: 2
- **Key Methods**: src.taskfile.cigen.gitea.GiteaActionsTarget._tag_var, src.taskfile.cigen.gitea.GiteaActionsTarget.generate
- **Inherits**: CITarget

### src.taskfile.models.PipelineConfig
> CI/CD pipeline configuration.
- **Methods**: 2
- **Key Methods**: src.taskfile.models.PipelineConfig.from_dict, src.taskfile.models.PipelineConfig.infer_from_tasks

### src.taskfile.runner.TaskRunError
> Raised when a task command fails.
- **Methods**: 1
- **Key Methods**: src.taskfile.runner.TaskRunError.__init__
- **Inherits**: Exception

### src.taskfile.cirunner.PipelineError
> Raised when a pipeline stage fails.
- **Methods**: 1
- **Key Methods**: src.taskfile.cirunner.PipelineError.__init__
- **Inherits**: Exception

### src.taskfile.cirunner.StageResult
> Result of running a single pipeline stage.
- **Methods**: 1
- **Key Methods**: src.taskfile.cirunner.StageResult.__init__

### src.taskfile.cigen.makefile.MakefileTarget
- **Methods**: 1
- **Key Methods**: src.taskfile.cigen.makefile.MakefileTarget.generate
- **Inherits**: CITarget

### src.taskfile.models.Task
> Single task definition.
- **Methods**: 1
- **Key Methods**: src.taskfile.models.Task.should_run_on

### src.taskfile.models.TaskfileConfig
> Parsed Taskfile configuration.
- **Methods**: 1
- **Key Methods**: src.taskfile.models.TaskfileConfig.from_dict

### src.taskfile.parser.TaskfileNotFoundError
> Raised when no Taskfile is found in the search path.
- **Methods**: 0
- **Inherits**: Exception

### src.taskfile.parser.TaskfileParseError
> Raised when Taskfile cannot be parsed.
- **Methods**: 0
- **Inherits**: Exception

### src.taskfile.models.ComposeConfig
> Compose-based deployment configuration.
- **Methods**: 0

## Data Transformation Functions

Key functions that process and transform data:

### src.taskfile.parser.validate_taskfile
> Validate a TaskfileConfig and return list of warnings.
- **Output to**: config.tasks.items, warnings.append, warnings.append, warnings.append, warnings.append

### src.taskfile.quadlet._parse_port
> Parse '8080:80' → ('8080', '80') or '80' → ('80', '80').
- **Output to**: None.split, len, str

### src.taskfile.quadlet._parse_memory_limit
> Extract memory limit from deploy.resources.limits.memory.

### src.taskfile.quadlet._parse_cpus_limit
> Extract CPU limit from deploy.resources.limits.cpus.
- **Output to**: str

### src.taskfile.cli.main.parse_var
> Parse --var KEY=VALUE pairs into a dict.
- **Output to**: item.split, val.strip, click.BadParameter, key.strip

### src.taskfile.cli.main.validate
> Validate the Taskfile without running anything.
- **Output to**: main.command, src.taskfile.parser.load_taskfile, src.taskfile.parser.validate_taskfile, console.print, console.print

## Behavioral Patterns

### recursion_resolve_dict
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: src.taskfile.compose.resolve_dict

## Public API Surface

Functions exposed as public API (no underscore prefix):

- `src.taskfile.models.TaskfileConfig.from_dict` - 54 calls
- `src.taskfile.cli.ci.ci_generate` - 41 calls
- `src.taskfile.cirunner.PipelineRunner.run` - 28 calls
- `src.taskfile.cli.deploy.deploy_cmd` - 28 calls
- `src.taskfile.runner.TaskfileRunner.run_task` - 25 calls
- `src.taskfile.models.PipelineConfig.from_dict` - 25 calls
- `src.taskfile.quadlet.compose_to_quadlet` - 24 calls
- `src.taskfile.cli.quadlet.quadlet_generate` - 19 calls
- `src.taskfile.cigen.makefile.MakefileTarget.generate` - 18 calls
- `src.taskfile.cli.ci.ci_run` - 17 calls
- `src.taskfile.runner.TaskfileRunner.list_tasks` - 16 calls
- `src.taskfile.cli.main.info` - 16 calls
- `src.taskfile.cli.quadlet.quadlet_upload` - 15 calls
- `src.taskfile.cli.main.init` - 12 calls
- `src.taskfile.cli.main.validate` - 12 calls
- `src.taskfile.parser.load_taskfile` - 11 calls
- `src.taskfile.cli.ci.ci_preview` - 11 calls
- `src.taskfile.compose.load_env_file` - 10 calls
- `src.taskfile.cli.main.main` - 10 calls
- `src.taskfile.compose.ComposeFile.get_traefik_labels` - 9 calls
- `src.taskfile.compose.resolve_variables` - 8 calls
- `src.taskfile.cirunner.PipelineRunner.list_stages` - 8 calls
- `src.taskfile.cli.main.run` - 8 calls
- `src.taskfile.compose.resolve_dict` - 7 calls
- `src.taskfile.runner.TaskfileRunner.run_command` - 7 calls
- `src.taskfile.cli.ci.ci_list` - 7 calls
- `src.taskfile.parser.find_taskfile` - 6 calls
- `src.taskfile.runner.TaskfileRunner.expand_variables` - 6 calls
- `src.taskfile.cli.ci.ci_targets` - 6 calls
- `src.taskfile.cli.main.list_tasks` - 6 calls
- `src.taskfile.cigen.gitlab.GitLabCITarget.generate` - 6 calls
- `src.taskfile.cigen.generate_ci` - 6 calls
- `src.taskfile.models.PipelineConfig.infer_from_tasks` - 6 calls
- `src.taskfile.parser.validate_taskfile` - 5 calls
- `src.taskfile.quadlet.generate_container_unit` - 5 calls
- `src.taskfile.cigen.jenkins.JenkinsTarget.generate` - 5 calls
- `src.taskfile.cigen.preview_ci` - 5 calls
- `src.taskfile.cigen.base.CITarget.write` - 4 calls
- `src.taskfile.cli.main.parse_var` - 4 calls
- `src.taskfile.cigen.drone.DroneCITarget.generate` - 4 calls

## System Interactions

How components interact:

```mermaid
graph TD
    from_dict --> cls
    from_dict --> get
    from_dict --> isinstance
    from_dict --> items
    ci_generate --> command
    ci_generate --> option
    ci_generate --> load_taskfile
    run --> _resolve_stages
    run --> _print_pipeline_head
    run --> time
    run --> enumerate
    run --> _print_summary
    deploy_cmd --> command
    deploy_cmd --> option
    deploy_cmd --> get
    run_task --> Text
    run_task --> append
    run_task --> print
    run_task --> time
    from_dict --> str
    quadlet_generate --> command
    quadlet_generate --> option
    generate --> sorted
    generate --> join
    generate --> items
    generate --> replace
    generate --> append
    ci_run --> command
    ci_run --> option
    ci_run --> load_taskfile
```

## Reverse Engineering Guidelines

1. **Entry Points**: Start analysis from the entry points listed above
2. **Core Logic**: Focus on classes with many methods
3. **Data Flow**: Follow data transformation functions
4. **Process Flows**: Use the flow diagrams for execution paths
5. **API Surface**: Public API functions reveal the interface

## Context for LLM

Maintain the identified architectural patterns and public API surface when suggesting changes.