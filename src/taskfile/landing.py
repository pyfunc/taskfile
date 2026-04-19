"""Landing page generator for desktop application distribution.

Generates static HTML landing pages with download links for desktop builds.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    pass

console = Console()


LANDING_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{APP_NAME}} — {{TAG}}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        header {
            text-align: center;
            padding: 3rem 0;
            color: white;
        }
        h1 {
            font-size: 3rem;
            margin-bottom: 0.5rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .version {
            font-size: 1.25rem;
            opacity: 0.9;
        }
        .badge {
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            margin-top: 1rem;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        .card h2 {
            color: #667eea;
            margin-bottom: 1rem;
            font-size: 1.5rem;
        }
        .downloads {
            display: grid;
            gap: 1rem;
            margin-top: 1rem;
        }
        .download-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem;
            background: #f8f9fa;
            border-radius: 8px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .download-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .platform {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-weight: 600;
        }
        .platform-icon {
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 500;
            transition: background 0.2s;
        }
        .btn:hover {
            background: #5a67d8;
        }
        .web-app {
            text-align: center;
            padding: 2rem;
        }
        .web-app .btn {
            font-size: 1.125rem;
            padding: 1rem 2rem;
        }
        footer {
            text-align: center;
            color: rgba(255,255,255,0.7);
            padding: 2rem 0;
            font-size: 0.875rem;
        }
        .release-info {
            color: #666;
            font-size: 0.875rem;
            margin-top: 0.5rem;
        }
        @media (max-width: 600px) {
            h1 { font-size: 2rem; }
            .container { padding: 1rem; }
            .card { padding: 1.5rem; }
            .download-item {
                flex-direction: column;
                gap: 1rem;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{{APP_NAME}}</h1>
            <div class="version">Version {{TAG}}</div>
            <span class="badge">Latest Release</span>
        </header>

        <div class="card">
            <h2>Desktop Downloads</h2>
            <div class="downloads">
                <div class="download-item">
                    <div class="platform">
                        <div class="platform-icon">🪟</div>
                        <span>Windows</span>
                    </div>
                    <a href="/releases/{{TAG}}/{{APP_NAME}}-{{TAG}}.exe" class="btn">
                        Download .exe
                    </a>
                </div>
                <div class="download-item">
                    <div class="platform">
                        <div class="platform-icon">🍎</div>
                        <span>macOS</span>
                    </div>
                    <a href="/releases/{{TAG}}/{{APP_NAME}}-{{TAG}}.dmg" class="btn">
                        Download .dmg
                    </a>
                </div>
                <div class="download-item">
                    <div class="platform">
                        <div class="platform-icon">🐧</div>
                        <span>Linux</span>
                    </div>
                    <a href="/releases/{{TAG}}/{{APP_NAME}}-{{TAG}}.AppImage" class="btn">
                        Download AppImage
                    </a>
                </div>
            </div>
            <p class="release-info">
                Released {{RELEASE_DATE}} | 
                <a href="/releases/{{TAG}}/RELEASE_NOTES.md">Release Notes</a>
            </p>
        </div>

        <div class="card web-app">
            <h2>Web Application</h2>
            <p style="margin-bottom: 1.5rem; color: #666;">
                Prefer to use {{APP_NAME}} in your browser? No installation required.
            </p>
            <a href="https://app.{{DOMAIN}}" class="btn">
                Open Web App →
            </a>
        </div>

        <footer>
            <p>© {{YEAR}} {{APP_NAME}}. All rights reserved.</p>
            <p style="margin-top: 0.5rem;">
                <a href="https://github.com/{{GITHUB_REPO}}" style="color: inherit;">GitHub</a> •
                <a href="/docs" style="color: inherit;">Documentation</a> •
                <a href="/support" style="color: inherit;">Support</a>
            </p>
        </footer>
    </div>
</body>
</html>
"""


def generate_landing_page(
    app_name: str,
    tag: str,
    domain: str,
    release_date: str = "today",
    year: str = "2026",
    github_repo: str = "",
) -> str:
    """Generate landing page HTML with download links.

    Args:
        app_name: Application name
        tag: Version tag (e.g., v1.0.0)
        domain: Domain name
        release_date: Release date string
        year: Copyright year
        github_repo: GitHub repository path (e.g., user/repo)

    Returns:
        HTML content as string
    """
    html = LANDING_TEMPLATE.replace("{{APP_NAME}}", app_name)
    html = html.replace("{{TAG}}", tag)
    html = html.replace("{{DOMAIN}}", domain)
    html = html.replace("{{RELEASE_DATE}}", release_date)
    html = html.replace("{{YEAR}}", year)
    html = html.replace("{{GITHUB_REPO}}", github_repo or f"{app_name.lower()}/{app_name.lower()}")
    return html


def build_landing_page(
    output_dir: str | Path,
    app_name: str,
    tag: str,
    domain: str,
    release_date: str = "today",
    year: str = "2026",
    github_repo: str = "",
) -> Path:
    """Build and save landing page to output directory.

    Args:
        output_dir: Directory to save the landing page
        app_name: Application name
        tag: Version tag
        domain: Domain name
        release_date: Release date
        year: Copyright year
        github_repo: GitHub repository path

    Returns:
        Path to generated index.html
    """
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    html = generate_landing_page(
        app_name=app_name,
        tag=tag,
        domain=domain,
        release_date=release_date,
        year=year,
        github_repo=github_repo,
    )

    index_path = outdir / "index.html"
    index_path.write_text(html, encoding="utf-8")

    console.print(f"  [green]✓[/] Landing page: {index_path}")
    return index_path


def create_landing_nginx_config(
    domain: str,
    landing_dir: str,
    releases_dir: str,
) -> str:
    """Generate nginx configuration for serving landing page and releases.

    Args:
        domain: Domain name
        landing_dir: Path to landing page directory
        releases_dir: Path to releases directory

    Returns:
        nginx configuration as string
    """
    return f"""server {{
    listen 80;
    server_name {domain};

    location / {{
        root {landing_dir};
        index index.html;
        try_files $uri $uri/ =404;
    }}

    location /releases/ {{
        alias {releases_dir}/;
        autoindex on;
        add_header Content-Disposition "attachment";
    }}

    # Redirect to HTTPS if using TLS
    # if ($scheme = http) {{
    #     return 301 https://$server_name$request_uri;
    # }}
}}
"""


def create_landing_compose_service(
    domain: str,
    landing_port: int = 8080,
    traefik_enabled: bool = True,
) -> dict:
    """Create docker-compose service definition for landing page.

    Args:
        domain: Domain name
        landing_port: Port to expose landing page
        traefik_enabled: Enable Traefik labels

    Returns:
        Docker compose service dictionary
    """
    service = {
        "image": "nginx:alpine",
        "container_name": "landing",
        "restart": "unless-stopped",
        "volumes": [
            "./dist/landing:/usr/share/nginx/html:ro",
            "./dist/releases:/usr/share/nginx/html/releases:ro",
        ],
        "ports": [f"{landing_port}:80"],
    }

    if traefik_enabled:
        service["labels"] = {
            "traefik.enable": "true",
            "traefik.http.routers.landing.rule": f"Host(`{domain}`)",
            "traefik.http.routers.landing.tls": "${TLS_ENABLED:-false}",
            "traefik.http.services.landing.loadbalancer.server.port": "80",
        }

    return service
