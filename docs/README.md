<!-- code2docs:start --># taskfile

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.9-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-825-green)
> **825** functions | **96** classes | **127** files | CC̄ = 4.2

> Auto-generated project documentation from source code analysis.

**Author:** Tom Sapletta  
**License:** Apache-2.0[(LICENSE)](./LICENSE)  
**Repository:** [https://github.com/pyfunc/taskfile](https://github.com/pyfunc/taskfile)

## Installation

### From PyPI

```bash
pip install taskfile
```

### From Source

```bash
git clone https://github.com/pyfunc/taskfile
cd taskfile
pip install -e .
```

### Optional Extras

```bash
pip install taskfile[ssh]    # ssh features
pip install taskfile[api]    # api features
pip install taskfile[llm]    # LLM integration (litellm)
pip install taskfile[dev]    # development tools
```

## Quick Start

### CLI Usage

```bash
# Generate full documentation for your project
taskfile ./my-project

# Only regenerate README
taskfile ./my-project --readme-only

# Preview what would be generated (no file writes)
taskfile ./my-project --dry-run

# Check documentation health
taskfile check ./my-project

# Sync — regenerate only changed modules
taskfile sync ./my-project
```

### Python API

```python
from taskfile import generate_readme, generate_docs, Code2DocsConfig

# Quick: generate README
generate_readme("./my-project")

# Full: generate all documentation
config = Code2DocsConfig(project_name="mylib", verbose=True)
docs = generate_docs("./my-project", config=config)
```

## Generated Output

When you run `taskfile`, the following files are produced:

```
<project>/
├── README.md                 # Main project README (auto-generated sections)
├── docs/
│   ├── api.md               # Consolidated API reference
│   ├── modules.md           # Module documentation with metrics
│   ├── architecture.md      # Architecture overview with diagrams
│   ├── dependency-graph.md  # Module dependency graphs
│   ├── coverage.md          # Docstring coverage report
│   ├── getting-started.md   # Getting started guide
│   ├── configuration.md    # Configuration reference
│   └── api-changelog.md    # API change tracking
├── examples/
│   ├── quickstart.py       # Basic usage examples
│   └── advanced_usage.py   # Advanced usage examples
├── CONTRIBUTING.md         # Contribution guidelines
└── mkdocs.yml             # MkDocs site configuration
```

## Configuration

Create `taskfile.yaml` in your project root (or run `taskfile init`):

```yaml
project:
  name: my-project
  source: ./
  output: ./docs/

readme:
  sections:
    - overview
    - install
    - quickstart
    - api
    - structure
  badges:
    - version
    - python
    - coverage
  sync_markers: true

docs:
  api_reference: true
  module_docs: true
  architecture: true
  changelog: true

examples:
  auto_generate: true
  from_entry_points: true

sync:
  strategy: markers    # markers | full | git-diff
  watch: false
  ignore:
    - "tests/"
    - "__pycache__"
```

## Sync Markers

taskfile can update only specific sections of an existing README using HTML comment markers:

```markdown
<!-- taskfile:start -->
# Project Title
... auto-generated content ...
<!-- taskfile:end -->
```

Content outside the markers is preserved when regenerating. Enable this with `sync_markers: true` in your configuration.

## Architecture

```
taskfile/
├── TODO/    ├── dns        ├── converters        ├── deploy_recipes        ├── watch        ├── provisioner        ├── landing    ├── taskfile/        ├── registry        ├── graph        ├── importer        ├── __main__        ├── health        ├── compose        ├── cirunner        ├── parser        ├── fleet        ├── ssh        ├── notifications        ├── cache        ├── scaffold/            ├── web            ├── minimal            ├── publish            ├── full            ├── podman            ├── multiplatform            ├── codereview            ├── llm_repair            ├── checks_placeholders            ├── fixop_adapter            ├── checks_infra            ├── checks_registry            ├── checks_ports            ├── checks_deploy        ├── quadlet        ├── diagnostics/            ├── models            ├── fixes            ├── report    ├── models            ├── checks_ssh            ├── checks            ├── error_presenter        ├── runner/            ├── functions            ├── failure            ├── classifier            ├── commands            ├── resolver            ├── explainer            ├── ssh        ├── models/        ├── deploy_utils            ├── core            ├── pipeline            ├── registry_cmds            ├── environment            ├── version            ├── docker_cmds            ├── diagnostics        ├── cli/            ├── task            ├── auth            ├── config            ├── health            ├── import_export            ├── quadlet            ├── explain_cmd            ├── ci            ├── cache_cmds            ├── api_cmd            ├── completion            ├── release            ├── setup            ├── deploy            ├── click_compat            ├── fleet            ├── info_cmd            ├── base            ├── drone            ├── gitlab            ├── makefile            ├── main        ├── cigen/            ├── jenkins            ├── dashboard            ├── e2e_cmd        ├── webui/            ├── gitea            ├── github            ├── server            ├── monitoring            ├── fixop_addon        ├── addons/            ├── redis_addon        ├── api/            ├── postgres                ├── wizards            ├── interactive/                ├── menu            ├── report            ├── release            ├── migrate            ├── provision            ├── report            ├── report            ├── report├── project    ├── run-codereview    ├── run-all    ├── run-multiplatform    ├── run-minimal    ├── run-saas-app            ├── ci-generate            ├── validate-deploy            ├── health            ├── deploy            ├── health-check            ├── ci-pipeline            ├── deploy            ├── health            ├── health            ├── handlers            ├── app            ├── models```

## API Overview

### Classes

- **`MakefileConverter`** — Convert between Taskfile and Makefile.
- **`GitHubActionsConverter`** — Convert between Taskfile and GitHub Actions workflows.
- **`NpmScriptsConverter`** — Convert between Taskfile and npm scripts.
- **`GitLabCIConverter`** — Convert between Taskfile and GitLab CI.
- **`DockerComposeConverter`** — Convert Taskfile docker tasks to docker-compose services.
- **`FileWatcher`** — Watch files for changes and trigger callbacks.
- **`ProvisionConfig`** — Configuration for VPS provisioning.
- **`VPSProvisioner`** — Idempotent VPS provisioner using SSH.
- **`TaskPackage`** — Represents a task package in the registry.
- **`RegistryClient`** — Client for interacting with the task registry.
- **`HealthCheckResult`** — Result of a single health check.
- **`HealthReport`** — Aggregated health check report.
- **`PortMapping`** — Represents a port mapping from docker-compose.
- **`ComposeFile`** — Parsed docker-compose.yml with environment resolution.
- **`PipelineError`** — Raised when a pipeline stage fails.
- **`PipelineRunner`** — Runs CI/CD pipeline stages locally using TaskfileRunner.
- **`StageResult`** — Result of running a single pipeline stage.
- **`TaskfileNotFoundError`** — Raised when no Taskfile is found in the search path.
- **`TaskfileParseError`** — Raised when Taskfile cannot be parsed.
- **`FleetApp`** — Container application definition for fleet devices.
- **`DeviceGroup`** — Group of devices sharing update strategy.
- **`Device`** — A single managed device in the fleet.
- **`FleetConfig`** — Parsed fleet.yml configuration.
- **`DeviceStatus`** — Status information for a single device.
- **`TaskCache`** — Manages caching of task outputs based on input file hashes.
- **`ServiceConfig`** — Type definition for a docker-compose service configuration.
- **`ProjectDiagnostics`** — Facade composing checks + fixes + report — backward compatible API.
- **`IssueCategory`** — Classification of diagnostic issues — helps users identify root cause.
- **`FixStrategy`** — How an issue can be resolved.
- **`Issue`** — Single diagnostic issue with category, severity, fix strategy, and context.
- **`DoctorReport`** — Aggregated report from a full doctor run.
- **`Severity`** — —
- **`Category`** — —
- **`FixStrategy`** — —
- **`Issue`** — A detected infrastructure problem.
- **`FixResult`** — Result of applying a fix.
- **`HostContext`** — SSH connection context for remote operations.
- **`ErrorPresenter`** — Formats runtime errors with context, diagnosis, and fix suggestions.
- **`CommandType`** — Classification of a command string for routing to the correct pipeline.
- **`TaskResolver`** — Pure-logic task resolver: variable expansion, filtering, dependency ordering.
- **`StepIssue`** — A potential problem detected in a step.
- **`ExplainStep`** — Analysis of a single command in the execution plan.
- **`ExplainReport`** — Full pre-run analysis report.
- **`TaskExplainer`** — Analyzes execution plan and explains what will happen.
- **`SSHResult`** — Result of an SSH operation.
- **`RemoteInfo`** — Information about the remote host.
- **`TaskRunError`** — Raised when a task command fails.
- **`TaskfileRunner`** — Executes tasks from a Taskfile configuration.
- **`PipelineStage`** — A stage in the CI/CD pipeline.
- **`PipelineConfig`** — CI/CD pipeline configuration.
- **`Environment`** — Deployment environment configuration.
- **`Platform`** — Target platform configuration (e.g. desktop, web, mobile).
- **`EnvironmentGroup`** — Group of environments sharing an update strategy (e.g. RPi fleet).
- **`DockerContainer`** — —
- **`IssueCategory`** — Old 4-category system — kept for backward compatibility.
- **`DiagnosticIssue`** — Old-style diagnostic issue — kept for backward compatibility.
- **`Function`** — Embedded function callable from tasks via @fn prefix.
- **`Task`** — Single task definition.
- **`ComposeConfig`** — Compose-based deployment configuration.
- **`TaskfileConfig`** — Parsed Taskfile configuration.
- **`SetupConfig`** — Configuration collected during setup process.
- **`DeployStrategy`** — Pure data class representing selected deploy strategy.
- **`Abort`** — Exception to signal that the application should exit.
- **`BadParameter`** — Exception raised for bad parameter values.
- **`ClickException`** — Base class for click exceptions.
- **`CITarget`** — Base class for CI/CD target generators.
- **`DroneCITarget`** — —
- **`GitLabCITarget`** — —
- **`MakefileTarget`** — —
- **`JenkinsTarget`** — —
- **`E2EResult`** — Single e2e test result.
- **`GiteaActionsTarget`** — —
- **`GitHubActionsTarget`** — —
- **`WebUIServer`** — Web UI server for taskfile.
- **`TaskfileHandler`** — HTTP request handler for taskfile web UI.
- **`TaskStatus`** — —
- **`DeployStrategy`** — —
- **`RunTaskRequest`** — Request to run one or more tasks.
- **`ValidateRequest`** — Request to validate a Taskfile.
- **`TaskInfo`** — Single task metadata.
- **`EnvironmentInfo`** — Single environment metadata.
- **`EnvironmentGroupInfo`** — Environment group metadata.
- **`PlatformInfo`** — Platform metadata.
- **`FunctionInfo`** — Embedded function metadata.
- **`PipelineStageInfo`** — Pipeline stage metadata.
- **`TaskfileInfo`** — Full Taskfile configuration metadata.
- **`ValidationResult`** — Taskfile validation result.
- **`CommandOutput`** — Output line from a running task.
- **`TaskRunResult`** — Result of a single task execution.
- **`RunResult`** — Result of a task run request.
- **`HealthResponse`** — API health check response.
- **`DoctorIssueInfo`** — Single diagnostic issue from doctor.
- **`DoctorRequest`** — Request options for the doctor endpoint.
- **`DoctorResponse`** — Full doctor diagnostics result.
- **`ErrorResponse`** — Error response.

### Functions

- `check_all(ctx, domains, containers)` — Run all infrastructure checks on a remote host.
- `check_host_dns(ctx, domain)` — Check if the host can resolve external domains.
- `check_container_dns(ctx, container, domain)` — Check if a container can resolve external domains.
- `check_systemd_resolved(ctx)` — Check if systemd-resolved is active and potentially blocking DNS.
- `fix_resolv_conf(ctx, nameservers)` — Write public DNS nameservers to /etc/resolv.conf on remote host.
- `fix_disable_systemd_resolved(ctx)` — Stop and disable systemd-resolved, then set static resolv.conf.
- `generate_container_resolv_conf(output_path, nameservers)` — Generate resolv.conf file for mounting into containers.
- `detect_format(file_path)` — Detect file format from path.
- `import_file(file_path, source_type)` — Import a file into Taskfile format.
- `export_file(config, target_type)` — Export Taskfile to another format.
- `expand_deploy_recipe(deploy_section, variables)` — Convert a deploy: section into a dict of task definitions.
- `watch_tasks(task_names, watch_paths, runner, debounce_ms)` — Watch files and run tasks on changes.
- `provision_vps(ip, ssh_key, ssh_user, domain)` — Convenience function for one-shot VPS provisioning.
- `generate_landing_page(app_name, tag, domain, release_date)` — Generate landing page HTML with download links.
- `build_landing_page(output_dir, app_name, tag, domain)` — Build and save landing page to output directory.
- `create_landing_nginx_config(domain, landing_dir, releases_dir)` — Generate nginx configuration for serving landing page and releases.
- `create_landing_compose_service(domain, landing_port, traefik_enabled)` — Create docker-compose service definition for landing page.
- `include_installed_tasks(taskfile_config)` — Include tasks from installed packages into taskfile config.
- `build_dependency_graph(config)` — Build a dependency graph from task configuration.
- `detect_cycles(graph)` — Detect cycles in dependency graph.
- `print_task_tree(config, root_task)` — Print task dependencies as a tree.
- `print_dependency_list(config)` — Print a flat list of tasks with their dependencies.
- `export_to_dot(config, output_path)` — Export dependency graph to DOT format for Graphviz.
- `import_file(source_path, source_type)` — Import a file and return Taskfile.yml content as string.
- `parse_github_actions(content, filename)` — Parse GitHub Actions workflow YAML into a Taskfile dict.
- `parse_gitlab_ci(content)` — Parse .gitlab-ci.yml into a Taskfile dict.
- `parse_makefile(content)` — Parse Makefile into a Taskfile dict.
- `check_http_endpoint(name, url, expected_status, timeout)` — Check HTTP endpoint health.
- `check_ssh_service(name, host, user, ssh_key)` — Check SSH service availability.
- `check_traefik_dashboard(host, user, ssh_key)` — Check Traefik dashboard via SSH tunnel.
- `run_health_checks(domain, ssh_host, ssh_user, ssh_key)` — Run comprehensive health checks for deployed services.
- `print_health_report(report)` — Print formatted health report to console.
- `health_check_all(domain, ssh_host, ssh_user, ssh_key)` — Run all health checks and print report.
- `load_env_file(path)` — Parse a .env file into a dict.
- `resolve_variables(text, variables)` — Resolve ${VAR}, ${VAR:-default}, and $VAR in a string.
- `resolve_dict(data, variables)` — Recursively resolve variables in a nested dict/list structure.
- `scan_nearby_taskfiles(start_dir)` — Scan for Taskfiles in nearby directories.
- `find_taskfile(start_dir)` — Find Taskfile.yml by walking up the directory tree.
- `load_taskfile(path)` — Load and parse a Taskfile.
- `validate_taskfile(config)` — Validate a TaskfileConfig and return list of warnings.
- `load_fleet(path)` — Load fleet.yml from the given path or search current directory.
- `save_fleet(config, path)` — Save FleetConfig back to fleet.yml.
- `check_device_status(config, device)` — Check the status of a single device via SSH.
- `fleet_status(config)` — Check status of all fleet devices (parallel).
- `print_fleet_status(statuses)` — Print fleet status as a rich table.
- `deploy_to_device(config, device, app_name, tag)` — Deploy a single app to a single device.
- `deploy_to_group(config, group_name, device_name, app_name)` — Deploy app to a group of devices using the group's update strategy.
- `add_device(config, name, host, group)` — Add a new device to the fleet config.
- `has_paramiko()` — Check if paramiko is available.
- `close_all()` — Close all pooled connections.
- `ssh_exec(env, command, timeout)` — Execute a command on remote host via embedded SSH (paramiko).
- `notify_task_complete(task_name, success, duration)` — Send desktop notification when task completes.
- `is_notification_available()` — Check if desktop notifications are available on this system.
- `get_project_hash(taskfile_path)` — Get a unique hash for the current project.
- `generate_taskfile(template)` — Generate a Taskfile.yml from a template.
- `is_available()` — Check if litellm is installed.
- `ask_llm_for_fix(issue, project_context)` — Ask LLM for a fix suggestion via litellm.
- `classify_runtime_error(exit_code, stderr, cmd)` — After a task command fails — classify whether it's a taskfile bug or app issue.
- `check_placeholder_values(config)` — Detect variables with placeholder values (example.com, changeme, etc.).
- `adapt_issue(fi, env_name)` — Convert a single fixop Issue to a taskfile Issue.
- `adapt_issues(fixop_issues, env_name)` — Convert a list of fixop Issues to taskfile Issues.
- `fixop_category_to_tag(fi)` — Map a fixop Issue's category to a legacy tag string (runtime/config/infra).
- `make_host_ctx(env)` — Build a fixop HostContext from a taskfile Environment.
- `check_ufw_forward_policy()` — Check if UFW default FORWARD policy allows container traffic.
- `check_container_dns()` — Check if Podman's default bridge DNS (10.88.0.1) can resolve external domains.
- `check_registry_access(config)` — Check if container image registries are reachable.
- `check_ports()` — Check docker-compose port conflicts and suggest .env fixes.
- `check_deploy_artifacts(config)` — Scan deploy/ directory for unresolved variables and placeholder values.
- `generate_container_unit(service_name, service, network_name, auto_update)` — Generate a .container Quadlet unit file content from a compose service.
- `generate_network_unit(network_name)` — Generate a .network Quadlet unit file.
- `generate_volume_unit(volume_name)` — Generate a .volume Quadlet unit file.
- `generate_resolv_conf(output_dir)` — Generate a resolv.conf with public DNS servers for Podman containers.
- `compose_to_quadlet(compose, output_dir, network_name, auto_update)` — Convert all services in a ComposeFile to Quadlet unit files.
- `apply_fixes(issues, interactive)` — Apply all fixable issues. Returns count of fixed issues.
- `apply_single_fix(issue, interactive)` — Apply a single fix. Returns True if fixed.
- `print_report(issues, categorized, show_teach)` — Print diagnostic report to console.
- `print_report_json(issues)` — Print report as JSON for CI pipelines.
- `get_report_dict(issues)` — Return structured report dict.
- `format_summary(report)` — Format a one-line summary string.
- `check_ssh_keys()` — Check SSH keys exist.
- `check_ssh_connectivity(config)` — Check SSH connectivity — delegates to fixop.
- `check_remote_health(config)` — Check remote host health — DNS, firewall, containers, disk, memory.
- `check_preflight()` — Check if required/common tools are available on the system.
- `check_taskfile()` — Check if Taskfile.yml exists and is valid YAML.
- `check_env_files()` — Check local .env files for common problems.
- `check_unresolved_variables(config)` — Find ${VAR} references without values — most common problem from TEST_REPORT.
- `check_ports()` — Check docker-compose port conflicts and suggest .env fixes.
- `check_dependent_files(config)` — Check that all files referenced in Taskfile (scripts, env_files) exist.
- `check_docker()` — Check if Docker is available.
- `check_ssh_keys()` — Check SSH keys exist.
- `check_ssh_connectivity(config)` — Check SSH connectivity — distinguish: missing key vs refused vs auth fail.
- `check_remote_health(config)` — Check remote host health — podman, disk space, container status.
- `check_git()` — Check if in git repo.
- `check_task_commands(config)` — Check if commands in tasks reference existing binaries.
- `check_examples(examples_dir)` — Validate all example directories. Returns list of result dicts.
- `validate_before_run(config, env_name, task_names)` — Quick pre-run validation — returns issues that would cause task failure.
- `run_function(runner, cmd, task)` — Execute an embedded function defined in the functions section.
- `run_inline_python(runner, cmd, task)` — Execute inline Python code.
- `classify_command(cmd)` — Classify a command string to determine its processing pipeline.
- `should_expand_globs(cmd)` — Determine if a command is safe for glob expansion via shlex.split.
- `has_glob_pattern(cmd)` — Quick check if a command string contains any glob characters.
- `run_command(runner, cmd, task)` — Execute a single command, locally or via SSH.
- `execute_script(runner, task, task_name)` — Execute an external script file referenced by task.script.
- `execute_commands(runner, task, task_name, start)` — Execute all commands in a task. Returns False if any failed (and not ignored).
- `print_explain_report(report, task_names, env_name)` — Print the --explain report to console.
- `print_teach_report(report, task_names, env_name, config)` — Print the --teach educational report.
- `is_local_command(cmd)` — Detect if command is prefixed with @local.
- `strip_local_prefix(cmd)` — Remove @local prefix from command.
- `is_remote_command(cmd)` — Detect if command is prefixed with @remote or @ssh.
- `strip_remote_prefix(cmd)` — Remove @remote/@ssh prefix from command.
- `wrap_ssh(cmd, env)` — Wrap command in SSH call to remote host.
- `is_push_command(cmd)` — Detect if command is prefixed with @push.
- `strip_push_prefix(cmd)` — Remove @push prefix from command.
- `is_pull_command(cmd)` — Detect if command is prefixed with @pull.
- `strip_pull_prefix(cmd)` — Remove @pull prefix from command.
- `wrap_scp_push(cmd, env)` — Build scp command: local files → remote destination.
- `wrap_scp_pull(cmd, env)` — Build scp command: remote files → local destination.
- `run_embedded_ssh(runner, cmd, task)` — Execute remote command via embedded SSH (paramiko).
- `load_env_file(path)` — Load a .env file into a dict. Skips comments and empty lines.
- `update_env_var(key, value, env_file)` — Update or append a variable in an .env file.
- `remove_env_var(key, env_file)` — Remove a variable from an .env file.
- `test_ssh_connection(host, user, port, timeout)` — Test SSH key-based connection to a remote host.
- `ssh_exec(host, command, user, port)` — Execute a command on a remote host via SSH.
- `setup_ssh_key(host, user, key_type)` — Generate SSH key if missing and copy to remote host.
- `check_remote_podman(host, user, port)` — Check if podman is installed on the remote host.
- `check_remote_disk(host, user, port)` — Check available disk space on the remote host.
- `list_remote_images(host, user, port)` — List container images on remote host.
- `check_remote_info(host, user, port)` — Gather full remote host information.
- `install_remote_podman(host, user, port)` — Install podman on the remote host (Debian/Ubuntu).
- `transfer_image_via_ssh(image, host, user, port)` — Transfer a Docker image to a remote host via SSH pipe.
- `transfer_images_via_ssh(images, host, user, port)` — Transfer multiple Docker images to a remote host.
- `deploy_container_remote(host, image, container_name, port_mapping)` — Deploy a container on a remote host.
- `stop_container_remote(host, container_name, user, port)` — Stop and remove a container on a remote host.
- `get_remote_logs(host, container_name, user, port)` — Get logs from a remote container.
- `get_remote_status(host, container_names, user, port)` — Get container status on a remote host.
- `clean_project(level, project_dir)` — Clean project artifacts.
- `pkg()` — 📦 Package management - install tasks from registry.
- `pkg_search(query, limit, registry)` — Search for packages in the registry.
- `pkg_install(package_name, version, save, no_save)` — Install a package from the registry.
- `pkg_list(all)` — List installed packages.
- `pkg_uninstall(package_name, yes)` — Uninstall a package.
- `pkg_info(package_name)` — Show information about a package.
- `version()` — Version management commands.
- `bump(ctx, part, dry_run, force)` — Bump version number (patch, minor, or major).
- `show(ctx)` — Show current project version.
- `set(ctx, new_version, dry_run, force)` — Set specific version number.
- `docker_group()` — 🐳 Docker helpers - inspect and stop containers, compose down, port management.
- `docker_ps_cmd()` — Show running docker containers (id, name, ports).
- `docker_stop_port_cmd(port, assume_yes)` — Stop all containers that publish the given host TCP port.
- `docker_stop_all_cmd(assume_yes)` — Stop all running docker containers.
- `docker_compose_down_cmd(compose_dir, assume_yes)` — Run `docker compose down` in the given directory (default: current).
- `validate_before_run(config, env_name, task_names)` — Backward-compatible wrapper — returns old DiagnosticIssue list.
- `auth()` — Registry authentication management.
- `auth_setup(registry)` — Interactive registry authentication setup.
- `auth_verify()` — Test all configured registry credentials.
- `health_cmd(ctx, domain, ssh_host, ssh_user)` — Check health of deployed services.
- `import_cmd(source, source_type, output_path, force)` — 📥 Import from Makefile, GitHub Actions, GitLab CI, npm scripts, etc.
- `export_cmd(ctx, target_type, output_path, workflow_name)` — 📤 Export Taskfile to other formats.
- `detect()` — 🔍 Detect build configuration files in current directory.
- `quadlet()` — **Generate and manage Podman Quadlet files** from docker-compose.yml.
- `quadlet_generate(ctx, compose_path, env_file, output_dir)` — **Generate Quadlet .container files** from docker-compose.yml.
- `quadlet_upload(ctx, quadlet_dir)` — Upload generated Quadlet files to remote server via SSH.
- `explain(ctx, task_name)` — **Explain what a task will do** — full execution plan without running.
- `ci()` — Generate CI/CD configs and run pipelines locally.
- `ci_generate(ctx, targets, gen_all, output_dir)` — Generate CI/CD config files from Taskfile.yml pipeline section.
- `ci_run(ctx, stages, skip_stages, stop_at)` — Run CI/CD pipeline stages locally.
- `ci_list(ctx)` — List pipeline stages defined in Taskfile.yml.
- `ci_preview(ctx, target)` — Preview generated CI/CD config without writing files.
- `ci_targets()` — List available CI/CD generation targets.
- `cache()` — 💾 Cache management - view, clear, or disable task caching.
- `cache_show()` — Show cache statistics and entries.
- `cache_clear(task_name, clear_all)` — Clear cache entries.
- `api()` — Manage the Taskfile REST API server.
- `api_serve(ctx, host, port, auto_reload)` — Start the Taskfile REST API server (FastAPI + Uvicorn).
- `api_openapi(ctx, output_path)` — Print or save the OpenAPI specification (JSON).
- `get_task_names(ctx, param, incomplete)` — Shell completion for task names.
- `get_environment_names(ctx, param, incomplete)` — Shell completion for environment names.
- `get_platform_names(ctx, param, incomplete)` — Shell completion for platform names.
- `generate_completion_script(shell)` — Generate shell completion script for taskfile.
- `release(ctx, tag_version, skip_desktop, skip_landing)` — Full release — build all, deploy all, update landing.
- `rollback(ctx, target_tag, domain, dry_run)` — Rollback to previous version.
- `setup(ip, ssh_key, user, domain)` — One-command VPS setup: SSH key → provision → deploy.
- `deploy_cmd(ctx, compose_override)` — Full deploy pipeline: build → push → generate Quadlet → upload → restart.
- `confirm(text, default, abort, prompt_suffix)` — Prompt for confirmation (yes/no question).
- `prompt(text, default, type, value_proc)` — Prompt for user input.
- `version_option(version, prog_name, message, help)` — Add a --version option to the command.
- `fleet()` — Manage a fleet of devices (RPi, edge nodes, kiosks).
- `fleet_status_cmd(ctx, group)` — Show status of all remote environments (SSH-based health check).
- `fleet_repair_cmd(ctx, env_name, auto_fix)` — Diagnose and repair a remote device.
- `fleet_list_cmd(ctx)` — List all remote environments and environment groups.
- `info(ctx, task_name)` — Show detailed info about a specific task.
- `register_target(name)` — —
- `parse_var(ctx, param, value)` — Parse --var KEY=VALUE pairs into a dict.
- `main(ctx, taskfile_path, env_name, env_group)` — **taskfile** — Universal task runner with multi-environment deploy.
- `run(ctx, tasks, run_tags, explain)` — **Run one or more tasks** defined in Taskfile.yml.
- `list_tasks(ctx)` — **List available tasks and environments** from Taskfile.yml.
- `validate(ctx, check_files, show_deps)` — **Validate the Taskfile** without running anything.
- `import_cmd(source, source_type, output_path, force)` — Import CI/CD config, Makefile, or script INTO Taskfile.yml.
- `generate_ci(config, target, project_dir)` — Generate CI/CD config for a specific target platform.
- `generate_all_ci(config, project_dir, targets)` — Generate CI/CD configs for multiple targets.
- `list_targets()` — Return list of (name, output_path, description) for all registered targets.
- `preview_ci(config, target)` — Generate CI/CD config content without writing to disk.
- `get_dashboard_html()` — Return the full dashboard HTML page.
- `e2e_cmd(ctx, check_only, url, port_web)` — **🧪 End-to-end tests** for services and IaC.
- `serve_dashboard(port, open_browser)` — Start the web dashboard.
- `generate_tasks(config)` — Generate monitoring tasks from addon config.
- `generate_tasks(config)` — Generate fixop tasks from addon config.
- `expand_addons(addons_section)` — Expand addons: list into a dict of raw task definitions.
- `generate_tasks(config)` — Generate Redis management tasks from addon config.
- `generate_tasks(config)` — Generate PostgreSQL management tasks from addon config.
- `doctor(fix, verbose, report, check_examples_flag)` — **🔧 Diagnose project** — 5-layer self-healing diagnostics.
- `init(template, force, interactive)` — **✨ Create a new Taskfile.yml** with interactive setup.
- `setup()` — **🛠️ Setup project** — hosts, env, dependencies.
- `hosts(env_file)` — **Configure deployment hosts** (staging/prod) interactively.
- `env(env_file)` — **Configure environment variables** (.env) interactively.
- `prod(env_file)` — **Interactive production server setup** — SSH, podman, .env.
- `watch(ctx, tasks, path, debounce)` — **👁️ Watch files** and run tasks on changes.
- `graph(ctx, task_name, dot, output)` — **🕸️ Show task dependency graph**.
- `serve(port, no_browser)` — **🌐 Start web dashboard** for managing tasks.
- `clean(level, assume_yes)` — **🧹 Clean project artifacts**.
- `push(images, host, user, runtime)` — **📦 Push Docker images to remote server** via SSH.
- `main()` — —
- `run(cmd, check)` — Run shell command, print it, return exit code.
- `main()` — —
- `main()` — —
- `ssh_run(host, user, cmd, check)` — Run a command on remote host via SSH.
- `main()` — —
- `main()` — —
- `generate_report()` — Build a deployment report from environment variables.
- `generate_report()` — Build a deployment report from environment variables.
- `run_example()` — —
- `build()` — —
- `test_app()` — —
- `deploy_staging()` — —
- `health_check()` — —
- `create_app(taskfile_path)` — Create and configure the FastAPI application.


## Project Structure

📦 `TODO` (1 functions)
📄 `TODO.dns` (6 functions)
📄 `TODO.models` (3 functions, 6 classes)
📄 `examples.functions-embed.scripts.health`
📄 `examples.functions-embed.scripts.report` (1 functions)
📄 `examples.import-cicd.sources.deploy` (4 functions)
📄 `examples.mega-saas-v2.scripts.health`
📄 `examples.mega-saas-v2.scripts.report` (1 functions)
📄 `examples.mega-saas.scripts.health`
📄 `examples.mega-saas.scripts.report` (1 functions)
📄 `examples.multiplatform.scripts.ci-generate`
📄 `examples.multiplatform.scripts.validate-deploy`
📄 `examples.run-all` (1 functions)
📄 `examples.run-codereview`
📄 `examples.run-minimal`
📄 `examples.run-multiplatform`
📄 `examples.run-saas-app`
📄 `examples.script-extraction.scripts.ci-pipeline`
📄 `examples.script-extraction.scripts.deploy`
📄 `examples.script-extraction.scripts.health-check`
📄 `examples.script-extraction.scripts.migrate` (1 functions)
📄 `examples.script-extraction.scripts.provision` (2 functions)
📄 `examples.script-extraction.scripts.release` (2 functions)
📄 `examples.script-extraction.scripts.report` (1 functions)
📄 `project`
📦 `src.taskfile`
📄 `src.taskfile.__main__`
📦 `src.taskfile.addons` (2 functions)
📄 `src.taskfile.addons.fixop_addon` (1 functions)
📄 `src.taskfile.addons.monitoring` (1 functions)
📄 `src.taskfile.addons.postgres` (1 functions)
📄 `src.taskfile.addons.redis_addon` (1 functions)
📦 `src.taskfile.api`
📄 `src.taskfile.api.app` (15 functions)
📄 `src.taskfile.api.models` (20 classes)
📄 `src.taskfile.cache` (13 functions, 1 classes)
📦 `src.taskfile.cigen` (4 functions)
📄 `src.taskfile.cigen.base` (9 functions, 1 classes)
📄 `src.taskfile.cigen.drone` (5 functions, 1 classes)
📄 `src.taskfile.cigen.gitea` (2 functions, 1 classes)
📄 `src.taskfile.cigen.github` (7 functions, 1 classes)
📄 `src.taskfile.cigen.gitlab` (8 functions, 1 classes)
📄 `src.taskfile.cigen.jenkins` (2 functions, 1 classes)
📄 `src.taskfile.cigen.makefile` (1 functions, 1 classes)
📄 `src.taskfile.cirunner` (9 functions, 3 classes)
📦 `src.taskfile.cli`
📄 `src.taskfile.cli.api_cmd` (3 functions)
📄 `src.taskfile.cli.auth` (7 functions)
📄 `src.taskfile.cli.cache_cmds` (3 functions)
📄 `src.taskfile.cli.ci` (6 functions)
📄 `src.taskfile.cli.click_compat` (5 functions, 3 classes)
📄 `src.taskfile.cli.completion` (4 functions)
📄 `src.taskfile.cli.deploy` (18 functions, 1 classes)
📄 `src.taskfile.cli.diagnostics` (4 functions, 2 classes)
📄 `src.taskfile.cli.docker_cmds` (9 functions, 1 classes)
📄 `src.taskfile.cli.e2e_cmd` (18 functions, 1 classes)
📄 `src.taskfile.cli.explain_cmd` (8 functions)
📄 `src.taskfile.cli.fleet` (18 functions)
📄 `src.taskfile.cli.health` (1 functions)
📄 `src.taskfile.cli.import_export` (3 functions)
📄 `src.taskfile.cli.info_cmd` (3 functions)
📦 `src.taskfile.cli.interactive`
📄 `src.taskfile.cli.interactive.menu` (9 functions)
📄 `src.taskfile.cli.interactive.wizards` (26 functions, 1 classes)
📄 `src.taskfile.cli.main` (25 functions)
📄 `src.taskfile.cli.quadlet` (6 functions)
📄 `src.taskfile.cli.registry_cmds` (6 functions)
📄 `src.taskfile.cli.release` (15 functions)
📄 `src.taskfile.cli.setup` (15 functions, 1 classes)
📄 `src.taskfile.cli.version` (11 functions)
📄 `src.taskfile.compose` (12 functions, 2 classes)
📄 `src.taskfile.converters` (11 functions, 5 classes)
📄 `src.taskfile.deploy_recipes` (17 functions)
📄 `src.taskfile.deploy_utils` (18 functions, 2 classes)
📦 `src.taskfile.diagnostics` (29 functions, 1 classes)
📄 `src.taskfile.diagnostics.checks` (24 functions)
📄 `src.taskfile.diagnostics.checks_deploy` (2 functions)
📄 `src.taskfile.diagnostics.checks_infra` (2 functions)
📄 `src.taskfile.diagnostics.checks_placeholders` (7 functions)
📄 `src.taskfile.diagnostics.checks_ports` (10 functions)
📄 `src.taskfile.diagnostics.checks_registry` (9 functions)
📄 `src.taskfile.diagnostics.checks_ssh` (3 functions)
📄 `src.taskfile.diagnostics.fixes` (10 functions)
📄 `src.taskfile.diagnostics.fixop_adapter` (4 functions)
📄 `src.taskfile.diagnostics.llm_repair` (5 functions)
📄 `src.taskfile.diagnostics.models` (3 functions, 4 classes)
📄 `src.taskfile.diagnostics.report` (11 functions)
📄 `src.taskfile.fleet` (16 functions, 5 classes)
📄 `src.taskfile.graph` (6 functions)
📄 `src.taskfile.health` (10 functions, 2 classes)
📄 `src.taskfile.importer` (20 functions)
📄 `src.taskfile.landing` (4 functions)
📦 `src.taskfile.models`
📄 `src.taskfile.models.config` (15 functions, 2 classes)
📄 `src.taskfile.models.environment` (2 functions, 3 classes)
📄 `src.taskfile.models.pipeline` (2 functions, 2 classes)
📄 `src.taskfile.models.task` (3 functions, 2 classes)
📄 `src.taskfile.notifications` (5 functions)
📄 `src.taskfile.parser` (19 functions, 2 classes)
📄 `src.taskfile.provisioner` (12 functions, 2 classes)
📄 `src.taskfile.quadlet` (24 functions, 1 classes)
📄 `src.taskfile.registry` (14 functions, 2 classes)
📦 `src.taskfile.runner`
📄 `src.taskfile.runner.classifier` (4 functions, 1 classes)
📄 `src.taskfile.runner.commands` (29 functions)
📄 `src.taskfile.runner.core` (34 functions, 2 classes)
📄 `src.taskfile.runner.error_presenter` (12 functions, 1 classes)
📄 `src.taskfile.runner.explainer` (14 functions, 4 classes)
📄 `src.taskfile.runner.failure` (12 functions)
📄 `src.taskfile.runner.functions` (7 functions)
📄 `src.taskfile.runner.resolver` (14 functions, 1 classes)
📄 `src.taskfile.runner.ssh` (12 functions)
📦 `src.taskfile.scaffold` (2 functions)
📄 `src.taskfile.scaffold.codereview`
📄 `src.taskfile.scaffold.full`
📄 `src.taskfile.scaffold.minimal`
📄 `src.taskfile.scaffold.multiplatform`
📄 `src.taskfile.scaffold.podman`
📄 `src.taskfile.scaffold.publish`
📄 `src.taskfile.scaffold.web`
📄 `src.taskfile.ssh` (6 functions)
📄 `src.taskfile.watch` (7 functions, 1 classes)
📦 `src.taskfile.webui`
📄 `src.taskfile.webui.dashboard` (1 functions)
📄 `src.taskfile.webui.handlers` (10 functions, 1 classes)
📄 `src.taskfile.webui.server` (4 functions, 1 classes)

## Requirements

- Python >= >=3.9
- pyyaml >=6.0- click >=8.0- rich >=13.0- clickmd >=1.1.1- fixop >=0.1.0

## Contributing

**Contributors:**
- Tom Softreck <tom@sapletta.com>
- Tom Sapletta <tom-sapletta-com@users.noreply.github.com>

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/pyfunc/taskfile
cd taskfile

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Documentation

- 📖 [Full Documentation](https://github.com/pyfunc/taskfile/tree/main/docs) — API reference, module docs, architecture
- 🚀 [Getting Started](https://github.com/pyfunc/taskfile/blob/main/docs/getting-started.md) — Quick start guide
- 📚 [API Reference](https://github.com/pyfunc/taskfile/blob/main/docs/api.md) — Complete API documentation
- 🔧 [Configuration](https://github.com/pyfunc/taskfile/blob/main/docs/configuration.md) — Configuration options
- 💡 [Examples](./examples) — Usage examples and code samples

### Generated Files

| Output | Description | Link |
|--------|-------------|------|
| `README.md` | Project overview (this file) | — |
| `docs/api.md` | Consolidated API reference | [View](./docs/api.md) |
| `docs/modules.md` | Module reference with metrics | [View](./docs/modules.md) |
| `docs/architecture.md` | Architecture with diagrams | [View](./docs/architecture.md) |
| `docs/dependency-graph.md` | Dependency graphs | [View](./docs/dependency-graph.md) |
| `docs/coverage.md` | Docstring coverage report | [View](./docs/coverage.md) |
| `docs/getting-started.md` | Getting started guide | [View](./docs/getting-started.md) |
| `docs/configuration.md` | Configuration reference | [View](./docs/configuration.md) |
| `docs/api-changelog.md` | API change tracking | [View](./docs/api-changelog.md) |
| `CONTRIBUTING.md` | Contribution guidelines | [View](./CONTRIBUTING.md) |
| `examples/` | Usage examples | [Browse](./examples) |
| `mkdocs.yml` | MkDocs configuration | — |

<!-- code2docs:end -->