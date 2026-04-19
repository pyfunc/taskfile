from __future__ import annotations
import sys
import clickmd as click
from taskfile.parser import load_taskfile, TaskfileNotFoundError, TaskfileParseError
from taskfile.cli.main import main, console


@main.group()
def ci():
    """Generate CI/CD configs and run pipelines locally.

    \b
    Generate:  taskfile ci generate --target github
    Run local: taskfile ci run
    Preview:   taskfile ci preview --target gitlab
    """
    pass


@ci.command(name="generate")
@click.option(
    "--target",
    "targets",
    multiple=True,
    help="CI platform: github, gitlab, gitea, drone, jenkins, makefile (repeatable)",
)
@click.option("--all", "gen_all", is_flag=True, help="Generate for all platforms")
@click.option("-o", "--output", "output_dir", default=".", help="Output project directory")
@click.pass_context
def ci_generate(ctx, targets, gen_all, output_dir):
    """Generate CI/CD config files from Taskfile.yml pipeline section.

    \b
    Examples:
        taskfile ci generate --target github
        taskfile ci generate --target github --target gitlab
        taskfile ci generate --all
        taskfile ci generate --target makefile

    \b
    Supported targets:
        github   → .github/workflows/taskfile.yml
        gitlab   → .gitlab-ci.yml
        gitea    → .gitea/workflows/taskfile.yml
        drone    → .drone.yml
        jenkins  → Jenkinsfile
        makefile → Makefile
    """
    from taskfile.cigen import generate_ci, generate_all_ci, list_targets

    opts = ctx.obj or {}
    try:
        config = load_taskfile(opts.get("taskfile_path"))

        if not config.pipeline.stages:
            console.print("[yellow]⚠ No pipeline stages defined in Taskfile.yml[/]")
            console.print("[dim]  Add a 'pipeline' section or 'stage' field on tasks[/]")
            console.print()
            console.print("[dim]  Example:[/]")
            console.print("[dim]  pipeline:[/]")
            console.print("[dim]    stages:[/]")
            console.print("[dim]      - name: test[/]")
            console.print("[dim]        tasks: [lint, test][/]")
            console.print("[dim]      - name: build[/]")
            console.print("[dim]        tasks: [build, push][/]")
            console.print("[dim]        docker_in_docker: true[/]")
            console.print("[dim]      - name: deploy[/]")
            console.print("[dim]        tasks: [deploy][/]")
            console.print("[dim]        env: prod[/]")
            console.print("[dim]        when: manual[/]")
            sys.exit(1)

        console.print("[bold]Generating CI/CD configs from Taskfile.yml[/]")
        stages_info = " → ".join(s.name for s in config.pipeline.stages)
        console.print(f"  Pipeline: {stages_info}\n")

        if gen_all:
            generated = generate_all_ci(config, output_dir)
        elif targets:
            generated = []
            for t in targets:
                path = generate_ci(config, t, output_dir)
                generated.append(path)
        else:
            # Default: generate for common platforms
            console.print("[yellow]No target specified. Use --target or --all[/]")
            console.print()
            console.print("[bold]Available targets:[/]")
            for name, path, desc in list_targets():
                console.print(f"  [green]{name:12s}[/] → {path:40s} [dim]({desc})[/]")
            sys.exit(0)

        console.print(f"\n[green]✓ Generated {len(generated)} CI/CD config(s)[/]")
        console.print(
            "[dim]  All configs call 'taskfile' — your pipeline logic stays in Taskfile.yml[/]"
        )

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@ci.command(name="run")
@click.option("--stage", "stages", multiple=True, help="Run specific stage(s) only")
@click.option("--skip", "skip_stages", multiple=True, help="Skip specific stage(s)")
@click.option("--stop-at", default=None, help="Stop after this stage")
@click.pass_context
def ci_run(ctx, stages, skip_stages, stop_at):
    """Run CI/CD pipeline stages locally.

    Runs the same pipeline that would run on GitHub/GitLab/etc,
    but directly on your machine. No runner needed.

    \b
    Examples:
        taskfile ci run                           # full pipeline
        taskfile ci run --stage test              # only test stage
        taskfile ci run --stage test --stage build
        taskfile ci run --skip deploy             # all except deploy
        taskfile ci run --stop-at build           # test + build, skip deploy
        taskfile --env prod ci run --stage deploy # deploy stage with prod env
        taskfile --dry-run ci run                 # preview commands
    """
    from taskfile.cirunner import PipelineRunner

    opts = ctx.obj or {}
    try:
        config = load_taskfile(opts.get("taskfile_path"))
        runner = PipelineRunner(
            config=config,
            env_name=opts.get("env_name"),
            var_overrides=opts.get("var", {}),
            dry_run=opts.get("dry_run", False),
            verbose=opts.get("verbose", False),
        )

        stage_list = list(stages) if stages else None
        skip_list = list(skip_stages) if skip_stages else None

        success = runner.run(
            stage_filter=stage_list,
            skip_stages=skip_list,
            stop_at=stop_at,
        )
        sys.exit(0 if success else 1)

    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@ci.command(name="list")
@click.pass_context
def ci_list(ctx):
    """List pipeline stages defined in Taskfile.yml."""
    from taskfile.cirunner import PipelineRunner

    opts = ctx.obj or {}
    try:
        config = load_taskfile(opts.get("taskfile_path"))
        runner = PipelineRunner(config=config)
        runner.list_stages()
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@ci.command(name="preview")
@click.option("--target", required=True, help="CI platform to preview")
@click.pass_context
def ci_preview(ctx, target):
    """Preview generated CI/CD config without writing files.

    \b
    Examples:
        taskfile ci preview --target github
        taskfile ci preview --target gitlab
    """
    from taskfile.cigen import preview_ci

    opts = ctx.obj or {}
    try:
        config = load_taskfile(opts.get("taskfile_path"))
        content = preview_ci(config, target)
        console.print(f"[bold]Preview: {target}[/]\n")
        console.print(content)
    except (TaskfileNotFoundError, TaskfileParseError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@ci.command(name="targets")
def ci_targets():
    """List available CI/CD generation targets."""
    from taskfile.cigen import list_targets

    console.print("\n[bold]Available CI/CD targets:[/]")
    for name, path, desc in list_targets():
        console.print(f"  [green]{name:12s}[/] → {path:42s} [dim]{desc}[/]")
    console.print()
    console.print("[dim]Generate: taskfile ci generate --target <name>[/]")
