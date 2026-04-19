"""Generate HTML deployment report with environment variables."""

import datetime
import json
import os


def generate_report():
    """Build a deployment report from environment variables."""
    app = os.environ.get("APP_NAME", "mega-saas")
    tag = os.environ.get("TAG", "latest")
    env = os.environ.get("TASKFILE_ENV", "unknown")
    domain = os.environ.get("DOMAIN", "localhost")
    platform = os.environ.get("TASKFILE_PLATFORM", "web")
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    report = {
        "app": app,
        "version": tag,
        "environment": env,
        "domain": domain,
        "platform": platform,
        "timestamp": ts,
        "images": {
            "api": f"{os.environ.get('IMAGE_API', '?')}:{tag}",
            "web": f"{os.environ.get('IMAGE_WEB', '?')}:{tag}",
            "worker": f"{os.environ.get('IMAGE_WORKER', '?')}:{tag}",
        },
        "config": {
            "replicas": os.environ.get("REPLICAS", "2"),
            "log_level": os.environ.get("LOG_LEVEL", "info"),
            "redis": os.environ.get("REDIS_URL", ""),
        },
    }

    # Print JSON summary
    print(json.dumps(report, indent=2))

    # Write HTML report
    html = f"""<!DOCTYPE html>
<html>
<head><title>Deploy Report — {app} {tag}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 700px; margin: 2rem auto; }}
  h1 {{ color: #1a73e8; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background: #f5f5f5; }}
  .ok {{ color: green; }} .fail {{ color: red; }}
</style>
</head>
<body>
<h1>🚀 Deployment Report</h1>
<p><strong>{app}</strong> v{tag} → <code>{env}</code> ({domain})</p>
<p>Generated: {ts}</p>
<table>
  <tr><th>Key</th><th>Value</th></tr>
  <tr><td>Platform</td><td>{platform}</td></tr>
  <tr><td>Replicas</td><td>{report['config']['replicas']}</td></tr>
  <tr><td>Log Level</td><td>{report['config']['log_level']}</td></tr>
  <tr><td>API Image</td><td><code>{report['images']['api']}</code></td></tr>
  <tr><td>Web Image</td><td><code>{report['images']['web']}</code></td></tr>
  <tr><td>Worker Image</td><td><code>{report['images']['worker']}</code></td></tr>
</table>
</body>
</html>"""

    report_path = f"/tmp/{app}-deploy-report.html"
    with open(report_path, "w") as f:
        f.write(html)
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    generate_report()
