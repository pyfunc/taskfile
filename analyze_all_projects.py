#!/usr/bin/env python3
"""Analyze Taskfile.yml and app.doql.css across all semcod & oqlos projects.

Produces a CSV report with quality metrics and fix recommendations.
"""

import csv
import re
import sys
from pathlib import Path


SEMCOD_ROOT = Path.home() / "github" / "semcod"
OQLOS_ROOT = Path.home() / "github" / "oqlos"

# Folders to skip (not real projects)
SKIP_FOLDERS = {
    "2026", "docs", "project", "logs", "venv", ".venv",
    "pyqual-demo", "taskinity", "refactor_output",
    "iql-run-logs", "oql-run-logs",
}

# Standard tasks every project should have
STANDARD_TASKS = {"install", "test", "lint", "fmt", "build", "clean", "help", "all"}

# Standard workflows every project should have
STANDARD_WORKFLOWS = {"install", "test", "lint", "build", "clean", "help", "all"}

# Taskfile top-level keys
TASKFILE_EXPECTED_KEYS = {"version", "name", "description", "variables", "environments", "tasks"}


def parse_taskfile_tasks(path: Path) -> list[str]:
    """Parse task names from Taskfile.yml (only from tasks: section)."""
    content = path.read_text()
    tasks = []
    in_tasks = False
    for line in content.splitlines():
        if line.rstrip() == "tasks:":
            in_tasks = True
            continue
        if in_tasks:
            if line and not line[0].isspace():
                break
            m = re.match(r"^  ([a-z][a-z0-9_-]*):", line)
            if m:
                tasks.append(m.group(1))
    return tasks


def parse_taskfile_meta(path: Path) -> dict:
    """Parse Taskfile.yml metadata."""
    content = path.read_text()
    meta = {
        "has_version": bool(re.search(r"^version:", content, re.M)),
        "has_name": bool(re.search(r"^name:", content, re.M)),
        "has_description": bool(re.search(r"^description:", content, re.M)),
        "has_variables": bool(re.search(r"^variables:", content, re.M)),
        "has_environments": bool(re.search(r"^environments:", content, re.M)),
        "has_pipeline": bool(re.search(r"^pipeline:", content, re.M)),
        "has_tasks": bool(re.search(r"^tasks:", content, re.M)),
    }

    # Check for broken deps (## markers from bad Makefile import)
    broken_deps = re.findall(r"^\s+- '##'", content, re.M)
    meta["broken_deps_count"] = len(broken_deps)

    # Check tasks with no desc
    tasks_no_desc = 0
    in_tasks = False
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.rstrip() == "tasks:":
            in_tasks = True
            continue
        if in_tasks:
            if line and not line[0].isspace():
                break
            if re.match(r"^  [a-z][a-z0-9_-]*:", line):
                # Check next line for desc
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if not next_line.startswith("desc:"):
                        tasks_no_desc += 1
                else:
                    tasks_no_desc += 1
    meta["tasks_no_desc"] = tasks_no_desc

    # Check for empty cmds
    empty_cmds = 0
    for i, line in enumerate(lines):
        if line.strip() == "cmds:":
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if not next_line.strip().startswith("- "):
                    empty_cmds += 1
            else:
                empty_cmds += 1
    meta["empty_cmds"] = empty_cmds

    return meta


def parse_doql_workflows(path: Path) -> list[str]:
    """Parse workflow names from app.doql.css."""
    content = path.read_text()
    return re.findall(r'workflow\[name="([^"]+)"\]', content)


def parse_doql_meta(path: Path) -> dict:
    """Parse app.doql.css metadata."""
    content = path.read_text()
    meta = {
        "has_app": bool(re.search(r"^app\s*\{", content, re.M)),
        "has_app_name": bool(re.search(r'^\s+name:\s*"', content, re.M)),
        "has_app_version": bool(re.search(r'^\s+version:\s*"', content, re.M)),
        "has_interface": bool(re.search(r"^interface\[", content, re.M)),
        "has_entity": bool(re.search(r"^entity\[", content, re.M)),
        "has_database": bool(re.search(r"^database\[", content, re.M)),
        "has_deploy": bool(re.search(r"^deploy\s*\{", content, re.M)),
        "has_environment": bool(re.search(r"^environment\[", content, re.M)),
        "has_integration": bool(re.search(r"^integration\[", content, re.M)),
    }

    # Count entities
    entities = re.findall(r'entity\[name="([^"]+)"\]', content)
    meta["entity_count"] = len(entities)

    # Count databases
    databases = re.findall(r'database\[name="([^"]+)"\]', content)
    meta["database_count"] = len(databases)

    # Count interfaces
    interfaces = re.findall(r'interface\[type="([^"]+)"\]', content)
    meta["interface_count"] = len(interfaces)

    # Empty workflows (no steps)
    workflow_blocks = re.findall(
        r'workflow\[name="([^"]+)"\]\s*\{([^}]*(?:\n[^}]*)*)\}',
        content,
    )
    empty_workflows = []
    for name, body in workflow_blocks:
        if "step-" not in body:
            empty_workflows.append(name)
    meta["empty_workflows"] = empty_workflows

    # Check for entities without database section
    if entities and not databases:
        meta["entities_no_db"] = True
    else:
        meta["entities_no_db"] = False

    return meta


def analyze_project(project_path: Path, group: str) -> dict:
    """Analyze a single project and return a dict of metrics."""
    name = project_path.name
    result = {
        "group": group,
        "project": name,
        "path": str(project_path),
        # Taskfile
        "taskfile_exists": False,
        "taskfile_tasks_count": 0,
        "taskfile_tasks": "",
        "tf_has_version": False,
        "tf_has_name": False,
        "tf_has_description": False,
        "tf_has_variables": False,
        "tf_has_environments": False,
        "tf_has_pipeline": False,
        "tf_broken_deps": 0,
        "tf_tasks_no_desc": 0,
        "tf_empty_cmds": 0,
        # doql
        "doql_exists": False,
        "doql_workflows_count": 0,
        "doql_workflows": "",
        "doql_has_app": False,
        "doql_has_app_name": False,
        "doql_has_app_version": False,
        "doql_has_interface": False,
        "doql_entity_count": 0,
        "doql_database_count": 0,
        "doql_interface_count": 0,
        "doql_empty_workflows": "",
        "doql_entities_no_db": False,
        "doql_has_deploy": False,
        "doql_has_environment": False,
        # Sync
        "sync_tasks_missing_in_doql": "",
        "sync_workflows_missing_in_taskfile": "",
        # Issues & recommendations
        "issues": "",
        "recommendations": "",
    }

    tf_path = project_path / "Taskfile.yml"
    doql_path = project_path / "app.doql.css"

    taskfile_tasks = []
    doql_workflows = []

    # Analyze Taskfile.yml
    if tf_path.exists():
        result["taskfile_exists"] = True
        try:
            taskfile_tasks = parse_taskfile_tasks(tf_path)
            result["taskfile_tasks_count"] = len(taskfile_tasks)
            result["taskfile_tasks"] = "; ".join(taskfile_tasks)

            meta = parse_taskfile_meta(tf_path)
            result["tf_has_version"] = meta["has_version"]
            result["tf_has_name"] = meta["has_name"]
            result["tf_has_description"] = meta["has_description"]
            result["tf_has_variables"] = meta["has_variables"]
            result["tf_has_environments"] = meta["has_environments"]
            result["tf_has_pipeline"] = meta["has_pipeline"]
            result["tf_broken_deps"] = meta["broken_deps_count"]
            result["tf_tasks_no_desc"] = meta["tasks_no_desc"]
            result["tf_empty_cmds"] = meta["empty_cmds"]
        except Exception as e:
            result["issues"] += f"Taskfile parse error: {e}; "

    # Analyze app.doql.css
    if doql_path.exists():
        result["doql_exists"] = True
        try:
            doql_workflows = parse_doql_workflows(doql_path)
            result["doql_workflows_count"] = len(doql_workflows)
            result["doql_workflows"] = "; ".join(doql_workflows)

            meta = parse_doql_meta(doql_path)
            result["doql_has_app"] = meta["has_app"]
            result["doql_has_app_name"] = meta["has_app_name"]
            result["doql_has_app_version"] = meta["has_app_version"]
            result["doql_has_interface"] = meta["has_interface"]
            result["doql_entity_count"] = meta["entity_count"]
            result["doql_database_count"] = meta["database_count"]
            result["doql_interface_count"] = meta["interface_count"]
            result["doql_empty_workflows"] = "; ".join(meta["empty_workflows"])
            result["doql_entities_no_db"] = meta["entities_no_db"]
            result["doql_has_deploy"] = meta.get("has_deploy", False)
            result["doql_has_environment"] = meta.get("has_environment", False)
        except Exception as e:
            result["issues"] += f"doql parse error: {e}; "

    # Sync analysis
    task_set = set(taskfile_tasks)
    wf_set = set(doql_workflows)
    # Exclude import-makefile-hint from sync check
    wf_set_for_sync = wf_set - {"import-makefile-hint"}

    if result["taskfile_exists"] and result["doql_exists"]:
        missing_in_doql = sorted(task_set - wf_set)
        missing_in_tf = sorted(wf_set_for_sync - task_set)
        result["sync_tasks_missing_in_doql"] = "; ".join(missing_in_doql)
        result["sync_workflows_missing_in_taskfile"] = "; ".join(missing_in_tf)

    # Build issues list
    issues = []
    recommendations = []

    if not result["taskfile_exists"]:
        issues.append("Missing Taskfile.yml")
    if not result["doql_exists"]:
        issues.append("Missing app.doql.css")

    if result["tf_broken_deps"] > 0:
        issues.append(f"Broken deps (## markers): {result['tf_broken_deps']}")
    if result["tf_tasks_no_desc"] > 0:
        issues.append(f"Tasks without desc: {result['tf_tasks_no_desc']}")
    if result["tf_empty_cmds"] > 0:
        issues.append(f"Empty cmds blocks: {result['tf_empty_cmds']}")

    if result["doql_empty_workflows"]:
        issues.append(f"Empty workflows: {result['doql_empty_workflows']}")

    if result["sync_tasks_missing_in_doql"]:
        issues.append(f"Tasks missing in doql: {result['sync_tasks_missing_in_doql']}")
    if result["sync_workflows_missing_in_taskfile"]:
        issues.append(f"Workflows missing in Taskfile: {result['sync_workflows_missing_in_taskfile']}")

    # Recommendations
    if result["taskfile_exists"] and not result["tf_has_pipeline"]:
        recommendations.append("Add pipeline section for CI/CD")
    if result["doql_entities_no_db"]:
        recommendations.append("Has entities but no database section")
    if result["doql_exists"] and not result["doql_has_deploy"]:
        recommendations.append("Add deploy {} section")
    if result["doql_exists"] and not result["doql_has_environment"]:
        recommendations.append("Add environment[] sections")

    # Check standard tasks
    if result["taskfile_exists"]:
        missing_std = sorted(STANDARD_TASKS - task_set)
        if missing_std:
            recommendations.append(f"Missing standard tasks: {'; '.join(missing_std)}")

    # Check standard workflows
    if result["doql_exists"]:
        missing_std_wf = sorted(STANDARD_WORKFLOWS - wf_set)
        if missing_std_wf:
            recommendations.append(f"Missing standard workflows: {'; '.join(missing_std_wf)}")

    result["issues"] = " | ".join(issues)
    result["recommendations"] = " | ".join(recommendations)

    return result


def discover_projects(root: Path, group: str) -> list[dict]:
    """Discover and analyze all projects under root."""
    results = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        if d.name in SKIP_FOLDERS or d.name.startswith("."):
            continue
        # Must have at least one of the manifests
        has_tf = (d / "Taskfile.yml").exists()
        has_doql = (d / "app.doql.css").exists()
        if not has_tf and not has_doql:
            continue
        results.append(analyze_project(d, group))
    return results


def fix_broken_deps(tf_path: Path) -> int:
    """Remove broken dep lines (## comment markers imported from Makefile)."""
    content = tf_path.read_text()
    lines = content.splitlines()
    new_lines = []
    removed = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        # Pattern: deps: followed by lines like "- '##'" and single-word dep items
        # that are actually split comment words
        if line.strip() == "deps:":
            # Peek ahead to see if deps section has ## markers
            j = i + 1
            dep_lines = []
            has_broken = False
            while j < len(lines) and re.match(r"^\s+- ", lines[j]):
                dep_lines.append(lines[j])
                val = lines[j].strip()
                if val in ("- '##'", "- '## '", '- "##"', '- "## "'):
                    has_broken = True
                j += 1
            if has_broken:
                # Remove entire deps section (it's all broken comment words)
                removed += len(dep_lines)
                i = j
                continue
            else:
                new_lines.append(line)
                i += 1
                continue
        new_lines.append(line)
        i += 1

    if removed > 0:
        tf_path.write_text("\n".join(new_lines) + "\n")
    return removed


def fix_broken_help_cmds(tf_path: Path) -> bool:
    """Fix help task cmds that reference Makefile variables like $(MAKEFILE_LIST)."""
    content = tf_path.read_text()
    if "$(MAKEFILE_LIST)" not in content:
        return False

    name_match = re.search(r"^name:\s*(\S+)", content, re.M)
    proj_name = name_match.group(1) if name_match else "project"

    # Replace the broken help cmds
    pattern = (
        r"(  help:\n"
        r"    desc: '[^']*'\n"
        r"    cmds:\n)"
        r"(?:    - .*\$\(MAKEFILE_LIST\).*\n)"
        r"(?:    - awk .*\n)"
    )
    replacement = (
        rf"\g<1>"
        rf'    - echo "{proj_name} — available tasks:"\n'
        rf'    - echo ""\n'
        rf"    - taskfile list\n"
    )
    new_content = re.sub(pattern, replacement, content)
    if new_content != content:
        tf_path.write_text(new_content)
        return True
    return False


def add_missing_workflows(doql_path: Path, missing: list[str]) -> int:
    """Add missing workflow blocks to app.doql.css."""
    content = doql_path.read_text()
    added = 0
    for wf_name in missing:
        if f'workflow[name="{wf_name}"]' in content:
            continue
        step = _workflow_step(wf_name)
        block = f'\nworkflow[name="{wf_name}"] {{\n  trigger: "manual";\n  {step}\n}}\n'
        content += block
        added += 1
    if added > 0:
        doql_path.write_text(content)
    return added


def _workflow_step(name: str) -> str:
    """Return a sensible step for a standard workflow."""
    mapping = {
        "help": 'step-1: run cmd=taskfile list;',
        "all": 'step-1: run cmd=taskfile run install;\n  step-2: run cmd=taskfile run lint;\n  step-3: run cmd=taskfile run test;',
        "install": 'step-1: run cmd=pip install -e ".[dev]";',
        "test": 'step-1: run cmd=pytest -q;',
        "lint": 'step-1: run cmd=ruff check .;',
        "fmt": 'step-1: run cmd=ruff format .;',
        "build": 'step-1: run cmd=python -m build;',
        "clean": 'step-1: run cmd=rm -rf build/ dist/ *.egg-info;',
    }
    return mapping.get(name, f'step-1: run cmd=echo "TODO: implement {name}";')


def _task_template(name: str, proj_name: str) -> str:
    """Return a proper task template for standard tasks."""
    templates = {
        "help": (
            f'  help:\n'
            f'    desc: Show available tasks\n'
            f'    cmds:\n'
            f'    - echo "{proj_name} — available tasks:"\n'
            f'    - echo ""\n'
            f'    - taskfile list\n'
        ),
        "all": (
            f'  all:\n'
            f'    desc: Run install, lint, test\n'
            f'    cmds:\n'
            f'    - taskfile run install\n'
            f'    - taskfile run lint\n'
            f'    - taskfile run test\n'
        ),
        "install": (
            f'  install:\n'
            f'    desc: Install Python dependencies (editable)\n'
            f'    cmds:\n'
            f'    - pip install -e .[dev]\n'
        ),
        "test": (
            f'  test:\n'
            f'    desc: Run pytest suite\n'
            f'    cmds:\n'
            f'    - pytest -q\n'
        ),
        "lint": (
            f'  lint:\n'
            f'    desc: Run ruff lint check\n'
            f'    cmds:\n'
            f'    - ruff check .\n'
        ),
        "fmt": (
            f'  fmt:\n'
            f'    desc: Auto-format with ruff\n'
            f'    cmds:\n'
            f'    - ruff format .\n'
        ),
        "build": (
            f'  build:\n'
            f'    desc: Build wheel + sdist\n'
            f'    cmds:\n'
            f'    - python -m build\n'
        ),
        "clean": (
            f'  clean:\n'
            f'    desc: Remove build artefacts\n'
            f'    cmds:\n'
            f'    - rm -rf build/ dist/ *.egg-info\n'
        ),
    }
    return templates.get(
        name,
        f'  {name}:\n'
        f'    desc: "[from doql] workflow: {name}"\n'
        f'    cmds:\n'
        f'    - echo "TODO: implement {name}"\n'
    )


def add_missing_tasks(tf_path: Path, missing: list[str]) -> int:
    """Add missing task entries to Taskfile.yml."""
    content = tf_path.read_text()
    name_match = re.search(r"^name:\s*(\S+)", content, re.M)
    proj_name = name_match.group(1) if name_match else "project"
    added = 0
    for task_name in missing:
        if re.search(rf"^  {re.escape(task_name)}:", content, re.M):
            continue
        block = _task_template(task_name, proj_name)
        content += block
        added += 1
    if added > 0:
        tf_path.write_text(content)
    return added


def add_pipeline_section(tf_path: Path) -> bool:
    """Add a pipeline section if missing."""
    content = tf_path.read_text()
    if re.search(r"^pipeline:", content, re.M):
        return False

    # Find the name from the file
    name_match = re.search(r"^name:\s*(\S+)", content, re.M)
    proj_name = name_match.group(1) if name_match else "project"

    pipeline_block = f"""pipeline:
  stages:
    - name: build
      tasks:
        - build
    - name: test
      tasks:
        - lint
        - test
"""
    # Insert before tasks: section
    if "tasks:" in content:
        content = content.replace("\ntasks:", f"\n{pipeline_block}\ntasks:", 1)
    else:
        content += "\n" + pipeline_block

    tf_path.write_text(content)
    return True


def main():
    fix_mode = "--fix" in sys.argv
    csv_path = Path.home() / "github" / "projects_analysis.csv"

    print(f"Analyzing projects... (fix={fix_mode})")

    all_results = []
    all_results.extend(discover_projects(SEMCOD_ROOT, "semcod"))
    all_results.extend(discover_projects(OQLOS_ROOT, "oqlos"))

    # Apply fixes if requested
    fix_log = []
    if fix_mode:
        for r in all_results:
            p = Path(r["path"])
            tf_path = p / "Taskfile.yml"
            doql_path = p / "app.doql.css"

            # Fix 1: Remove broken deps
            if r["tf_broken_deps"] > 0 and tf_path.exists():
                removed = fix_broken_deps(tf_path)
                if removed:
                    fix_log.append(f"  {r['project']}: removed {removed} broken dep lines")

            # Fix 2: Fix broken help cmds (Makefile references)
            if tf_path.exists():
                if fix_broken_help_cmds(tf_path):
                    fix_log.append(f"  {r['project']}: fixed broken help cmds")

            # Fix 3: Add missing standard tasks to Taskfile.yml
            if tf_path.exists():
                task_set = set(parse_taskfile_tasks(tf_path))
                missing_std = sorted(STANDARD_TASKS - task_set)
                if missing_std:
                    added = add_missing_tasks(tf_path, missing_std)
                    if added:
                        fix_log.append(f"  {r['project']}: added {added} standard tasks ({', '.join(missing_std)})")

            # Fix 4: Add missing standard workflows to app.doql.css
            if doql_path.exists():
                wf_set = set(parse_doql_workflows(doql_path))
                missing_std_wf = sorted(STANDARD_WORKFLOWS - wf_set)
                if missing_std_wf:
                    added = add_missing_workflows(doql_path, missing_std_wf)
                    if added:
                        fix_log.append(f"  {r['project']}: added {added} standard workflows ({', '.join(missing_std_wf)})")

            # Fix 5: Sync remaining tasks -> workflows
            if tf_path.exists() and doql_path.exists():
                tasks_now = set(parse_taskfile_tasks(tf_path))
                wfs_now = set(parse_doql_workflows(doql_path))
                missing_in_doql = sorted(tasks_now - wfs_now)
                if missing_in_doql:
                    added = add_missing_workflows(doql_path, missing_in_doql)
                    if added:
                        fix_log.append(f"  {r['project']}: synced {added} tasks -> workflows")

            # Fix 6: Sync remaining workflows -> tasks
            if tf_path.exists() and doql_path.exists():
                tasks_now = set(parse_taskfile_tasks(tf_path))
                wfs_now = set(parse_doql_workflows(doql_path)) - {"import-makefile-hint"}
                missing_in_tf = sorted(wfs_now - tasks_now)
                if missing_in_tf:
                    added = add_missing_tasks(tf_path, missing_in_tf)
                    if added:
                        fix_log.append(f"  {r['project']}: synced {added} workflows -> tasks")

        if fix_log:
            print(f"\nFixes applied ({len(fix_log)}):")
            for line in fix_log:
                print(line)

            # Re-analyze after fixes
            all_results = []
            all_results.extend(discover_projects(SEMCOD_ROOT, "semcod"))
            all_results.extend(discover_projects(OQLOS_ROOT, "oqlos"))
        else:
            print("\nNo fixes needed.")

    # Write CSV
    if all_results:
        fieldnames = list(all_results[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)
        print(f"\nCSV written: {csv_path}")

    # Print summary
    total = len(all_results)
    with_issues = sum(1 for r in all_results if r["issues"])
    with_recs = sum(1 for r in all_results if r["recommendations"])

    print(f"\n{'='*70}")
    print(f"SUMMARY: {total} projects analyzed")
    print(f"  With issues:          {with_issues}")
    print(f"  With recommendations: {with_recs}")
    print(f"  Clean:                {total - with_issues}")

    if with_issues:
        print(f"\nPROJECTS WITH ISSUES:")
        for r in all_results:
            if r["issues"]:
                print(f"  [{r['group']}] {r['project']}: {r['issues']}")

    if with_recs:
        print(f"\nRECOMMENDATIONS:")
        for r in all_results:
            if r["recommendations"]:
                print(f"  [{r['group']}] {r['project']}: {r['recommendations']}")


if __name__ == "__main__":
    main()
