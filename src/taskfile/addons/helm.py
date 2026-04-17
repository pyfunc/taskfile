"""Helm addon — generates standard Kubernetes Helm chart tasks.

Generated tasks:
    helm-lint, helm-template, helm-diff, helm-install, helm-upgrade,
    helm-rollback, helm-status, helm-uninstall, helm-test, helm-package
"""

from __future__ import annotations


def generate_tasks(config: dict) -> dict[str, dict]:
    """Generate Helm management tasks from addon config."""
    release = config.get("release", "${RELEASE:-myapp}")
    chart = config.get("chart", "./charts/${APP_NAME}")
    namespace = config.get("namespace", "${NAMESPACE:-default}")
    values_file = config.get("values_file", "values.yml")
    extra_values = config.get("extra_values", [])
    registry = config.get("registry", "${REGISTRY}")
    timeout = config.get("timeout", "5m")

    values_flags = f"-f {values_file}"
    for v in extra_values:
        values_flags += f" -f {v}"
    set_flags = f"--set image.tag=${{TAG}} --set image.repository={registry}/${{APP_NAME}}"

    common_flags = f"{values_flags} {set_flags} --namespace {namespace}"

    return {
        "helm-lint": {
            "desc": "Lint Helm chart for errors",
            "tags": ["helm", "ci"],
            "cmds": [
                f"helm lint {chart} {values_flags}",
            ],
        },
        "helm-template": {
            "desc": "Render Helm templates (dry-run output)",
            "tags": ["helm"],
            "cmds": [
                f"helm template {release} {chart} {common_flags}",
            ],
        },
        "helm-diff": {
            "desc": "Show diff between deployed and pending (requires helm-diff plugin)",
            "tags": ["helm"],
            "condition": "helm plugin list | grep -q diff",
            "cmds": [
                f"helm diff upgrade {release} {chart} {common_flags}",
            ],
        },
        "helm-install": {
            "desc": "Install Helm release (first deploy)",
            "tags": ["helm", "deploy"],
            "cmds": [
                f"helm install {release} {chart} {common_flags} --timeout {timeout} --wait",
            ],
        },
        "helm-upgrade": {
            "desc": "Upgrade Helm release",
            "tags": ["helm", "deploy"],
            "cmds": [
                f"helm upgrade --install {release} {chart} {common_flags} --timeout {timeout} --wait",
            ],
        },
        "helm-rollback": {
            "desc": "Rollback Helm release to previous version",
            "tags": ["helm", "ops"],
            "cmds": [
                f"helm rollback {release} --namespace {namespace}",
            ],
        },
        "helm-status": {
            "desc": "Show Helm release status",
            "tags": ["helm", "ops"],
            "silent": True,
            "cmds": [
                f"helm status {release} --namespace {namespace}",
            ],
        },
        "helm-uninstall": {
            "desc": "Uninstall Helm release",
            "tags": ["helm"],
            "cmds": [
                f"helm uninstall {release} --namespace {namespace}",
            ],
        },
        "helm-test": {
            "desc": "Run Helm chart tests",
            "tags": ["helm", "test"],
            "cmds": [
                f"helm test {release} --namespace {namespace}",
            ],
        },
        "helm-package": {
            "desc": "Package Helm chart into .tgz",
            "tags": ["helm"],
            "cmds": [
                f"helm package {chart} --destination dist/",
            ],
        },
    }
