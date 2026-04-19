"""CLI command for starting the Taskfile REST API server."""

from __future__ import annotations

import sys

import clickmd as click
from rich.console import Console

from taskfile.cli.main import main

console = Console()


@main.group()
def api():
    """Manage the Taskfile REST API server.

    \b
    Start server:   taskfile api serve
    Show OpenAPI:   taskfile api openapi
    """
    pass


@api.command(name="serve")
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", "-p", default=8000, type=int, help="Bind port")
@click.option("--reload", "auto_reload", is_flag=True, help="Auto-reload on code changes")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
@click.pass_context
def api_serve(ctx, host: str, port: int, auto_reload: bool, no_browser: bool):
    """Start the Taskfile REST API server (FastAPI + Uvicorn).

    \b
    Provides:
        Swagger UI:  http://HOST:PORT/docs
        ReDoc:       http://HOST:PORT/redoc
        OpenAPI:     http://HOST:PORT/openapi.json

    \b
    Examples:
        taskfile api serve                    # Start on 0.0.0.0:8000
        taskfile api serve -p 3000           # Custom port
        taskfile api serve --reload          # Dev mode with auto-reload
        taskfile api serve --no-browser      # Don't open browser
    """
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error:[/] uvicorn is required for the API server.")
        console.print("[dim]Install with: pip install taskfile[api][/]")
        sys.exit(1)

    taskfile_path = ctx.obj.get("taskfile_path") if ctx.obj else None

    # Set taskfile path via environment for the app factory
    import os

    if taskfile_path:
        os.environ["TASKFILE_API_PATH"] = str(taskfile_path)

    console.print("[bold green]🚀 Starting Taskfile API server...[/]")
    console.print(f"[dim]  Host:     {host}:{port}[/]")
    console.print(
        f"[dim]  Docs:     http://{host if host != '0.0.0.0' else 'localhost'}:{port}/docs[/]"
    )
    console.print(
        f"[dim]  ReDoc:    http://{host if host != '0.0.0.0' else 'localhost'}:{port}/redoc[/]"
    )
    console.print(
        f"[dim]  OpenAPI:  http://{host if host != '0.0.0.0' else 'localhost'}:{port}/openapi.json[/]"
    )
    console.print()

    if not no_browser:
        import webbrowser
        import threading

        def open_browser():
            import time

            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{port}/docs")

        threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        "taskfile.api:app",
        host=host,
        port=port,
        reload=auto_reload,
        log_level="info",
    )


@api.command(name="openapi")
@click.option("-o", "--output", "output_path", default=None, help="Save to file")
@click.pass_context
def api_openapi(ctx, output_path: str | None):
    """Print or save the OpenAPI specification (JSON).

    \b
    Examples:
        taskfile api openapi                  # Print to stdout
        taskfile api openapi -o openapi.json  # Save to file
    """
    import json

    try:
        from taskfile.api import create_app
    except ImportError:
        console.print("[red]Error:[/] fastapi is required.")
        console.print("[dim]Install with: pip install taskfile[api][/]")
        sys.exit(1)

    taskfile_path = ctx.obj.get("taskfile_path") if ctx.obj else None
    app = create_app(taskfile_path)
    spec = app.openapi()
    spec_json = json.dumps(spec, indent=2, ensure_ascii=False)

    if output_path:
        from pathlib import Path

        Path(output_path).write_text(spec_json + "\n", encoding="utf-8")
        console.print(f"[green]✓ OpenAPI spec saved to {output_path}[/]")
    else:
        click.echo(spec_json)
