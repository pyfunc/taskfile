"""Terraform addon — generates standard IaC tasks.

Generated tasks:
    tf-init, tf-workspace, tf-validate, tf-plan, tf-apply, tf-destroy,
    tf-output, tf-state-list, tf-lint, tf-security, tf-cost, tf-clean
"""

from __future__ import annotations


def generate_tasks(config: dict) -> dict[str, dict]:
    """Generate Terraform management tasks from addon config."""
    tf_dir = config.get("tf_dir", "terraform")
    state_bucket = config.get("state_bucket", "${TF_STATE_BUCKET}")
    project = config.get("project", "${PROJECT}")
    workspace_var = config.get("workspace_var", "${TF_WORKSPACE}")
    region_var = config.get("region_var", "${AWS_REGION}")
    extra_vars = config.get("extra_vars", [])

    plan_var_flags = " ".join(f"-var='{v}=${{{v}}}'" for v in extra_vars)
    plan_flags = f"-out=tfplan {plan_var_flags}".strip()
    apply_flags = "-input=false -auto-approve"

    return {
        "tf-init": {
            "desc": "Initialize Terraform backend + providers",
            "tags": ["terraform", "setup"],
            "dir": tf_dir,
            "cmds": [
                f"terraform init"
                f" -backend-config=\"bucket={state_bucket}\""
                f" -backend-config=\"key={project}/{workspace_var}/terraform.tfstate\""
                f" -backend-config=\"region={region_var}\"",
            ],
        },
        "tf-workspace": {
            "desc": "Select or create Terraform workspace",
            "tags": ["terraform"],
            "dir": tf_dir,
            "deps": ["tf-init"],
            "cmds": [
                f"terraform workspace select {workspace_var} || terraform workspace new {workspace_var}",
            ],
        },
        "tf-validate": {
            "desc": "Validate Terraform config + format check",
            "tags": ["terraform", "ci"],
            "dir": tf_dir,
            "deps": ["tf-workspace"],
            "cmds": [
                "terraform validate",
                "terraform fmt -check -recursive",
            ],
        },
        "tf-plan": {
            "desc": "Generate Terraform execution plan",
            "tags": ["terraform"],
            "dir": tf_dir,
            "deps": ["tf-workspace"],
            "cmds": [
                f"terraform plan {plan_flags}",
            ],
        },
        "tf-apply": {
            "desc": "Apply infrastructure changes",
            "tags": ["terraform", "deploy"],
            "dir": tf_dir,
            "deps": ["tf-plan"],
            "cmds": [
                "terraform apply tfplan",
            ],
        },
        "tf-destroy": {
            "desc": "Destroy all infrastructure (use with caution!)",
            "tags": ["terraform", "destroy"],
            "dir": tf_dir,
            "deps": ["tf-workspace"],
            "cmds": [
                f"terraform destroy {plan_var_flags} -auto-approve",
            ],
        },
        "tf-output": {
            "desc": "Show Terraform outputs as JSON",
            "tags": ["terraform", "ops"],
            "dir": tf_dir,
            "silent": True,
            "cmds": ["terraform output -json"],
        },
        "tf-state-list": {
            "desc": "List all resources in Terraform state",
            "tags": ["terraform", "ops"],
            "dir": tf_dir,
            "cmds": ["terraform state list"],
        },
        "tf-lint": {
            "desc": "Lint Terraform (fmt + tflint)",
            "tags": ["terraform", "ci"],
            "dir": tf_dir,
            "ignore_errors": True,
            "cmds": [
                "terraform fmt -check -recursive",
                "tflint --recursive",
            ],
        },
        "tf-security": {
            "desc": "Security scan (checkov + tfsec)",
            "tags": ["terraform", "security"],
            "dir": tf_dir,
            "ignore_errors": True,
            "cmds": [
                "checkov -d .",
                "tfsec .",
            ],
        },
        "tf-cost": {
            "desc": "Estimate infrastructure cost (requires infracost)",
            "tags": ["terraform", "ops"],
            "dir": tf_dir,
            "condition": "command -v infracost >/dev/null 2>&1",
            "cmds": [
                f"infracost breakdown --path . --terraform-var-file=vars/{workspace_var}.tfvars",
            ],
        },
        "tf-clean": {
            "desc": "Remove local plan + state backup files",
            "tags": ["terraform"],
            "dir": tf_dir,
            "cmds": [
                "rm -f tfplan terraform.tfstate.backup",
                "rm -rf .terraform/",
            ],
        },
    }
