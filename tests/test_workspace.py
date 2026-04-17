"""Tests for taskfile.workspace module."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskfile.workspace import (
    compare_projects,
    discover_projects,
    filter_projects,
    validate_project,
    _parse_taskfile_tasks,
    _parse_doql_workflows,
    _is_project_folder,
)


def _make_project(tmp_path: Path, name: str, with_taskfile: bool = True, with_doql: bool = True, tasks: list[str] = None, workflows: list[str] = None) -> Path:
    """Helper: create a fake project directory."""
    proj = tmp_path / name
    proj.mkdir()
    # Add project marker
    (proj / "pyproject.toml").write_text("[project]\nname = \"test\"\n")

    if with_taskfile:
        tasks = tasks or ["install", "test", "build"]
        lines = [
            "version: '1'",
            f"name: {name}",
            "tasks:",
        ]
        for t in tasks:
            lines.extend([f"  {t}:", f"    cmds:", f"    - echo {t}"])
        (proj / "Taskfile.yml").write_text("\n".join(lines) + "\n")

    if with_doql:
        workflows = workflows or ["install", "test"]
        lines = [f'app {{ name: "{name}"; version: "0.1.0"; }}', ""]
        for wf in workflows:
            lines.append(f'workflow[name="{wf}"] {{')
            lines.append(f'  step-1: run cmd=echo {wf};')
            lines.append(f'}}')
            lines.append("")
        (proj / "app.doql.css").write_text("\n".join(lines))

    return proj


class TestParseTaskfileTasks:
    def test_parses_task_names(self):
        content = """version: '1'
tasks:
  install:
    cmds:
    - pip install
  test:
    cmds:
    - pytest
  build:
    cmds:
    - python -m build
"""
        tasks = _parse_taskfile_tasks(content)
        assert tasks == ["install", "test", "build"]

    def test_empty(self):
        assert _parse_taskfile_tasks("version: '1'\ntasks: {}") == []

    def test_ignores_environments_and_pipeline_keys(self):
        content = """version: '1'
name: test
environments:
  local:
    container_runtime: docker
pipeline:
  stages:
    - name: test
tasks:
  install:
    cmds:
    - pip install
  test:
    cmds:
    - pytest
"""
        tasks = _parse_taskfile_tasks(content)
        assert tasks == ["install", "test"]
        assert "local" not in tasks
        assert "stages" not in tasks


class TestParseDoqlWorkflows:
    def test_parses_workflow_names(self):
        content = '''
workflow[name="install"] { step-1: run cmd=x; }
workflow[name="test"] { step-1: run cmd=y; }
workflow[name="build"] { step-1: run cmd=z; }
'''
        workflows = _parse_doql_workflows(content)
        assert workflows == ["install", "test", "build"]

    def test_empty(self):
        assert _parse_doql_workflows("") == []


class TestIsProjectFolder:
    def test_pyproject_toml(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("")
        assert _is_project_folder(proj) is True

    def test_package_json(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "package.json").write_text("{}")
        assert _is_project_folder(proj) is True

    def test_empty_folder(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        assert _is_project_folder(proj) is False

    def test_only_readme(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "README.md").write_text("")
        assert _is_project_folder(proj) is False


class TestDiscoverProjects:
    def test_discovers_direct_subdirs(self, tmp_path):
        _make_project(tmp_path, "alpha")
        _make_project(tmp_path, "beta")

        projects = discover_projects(tmp_path, max_depth=1)
        names = [p.name for p in projects]
        assert "alpha" in names
        assert "beta" in names
        assert len(projects) == 2

    def test_respects_max_depth(self, tmp_path):
        # depth 1: direct subdir
        _make_project(tmp_path, "top")
        # depth 2: nested under a non-project folder
        group = tmp_path / "group"
        group.mkdir()
        _make_project(group, "nested")

        d1 = discover_projects(tmp_path, max_depth=1)
        assert {p.name for p in d1} == {"top"}

        d2 = discover_projects(tmp_path, max_depth=2)
        assert {p.name for p in d2} == {"top", "nested"}

    def test_deduplicates_by_name_keeps_shallower(self, tmp_path):
        """When same project name exists at depth 1 and depth 2, keep shallower."""
        _make_project(tmp_path, "myproj", tasks=["install", "test", "build"])
        # Create a deeper duplicate (e.g. archive/myproj)
        archive = tmp_path / "archive"
        archive.mkdir()
        _make_project(archive, "myproj", tasks=["install"])

        projects = discover_projects(tmp_path, max_depth=2)
        names = [p.name for p in projects]
        assert names.count("myproj") == 1
        # The shallow one should win
        myproj = [p for p in projects if p.name == "myproj"][0]
        assert myproj.path == tmp_path / "myproj"
        assert "build" in myproj.taskfile_tasks

    def test_excludes_hidden_and_venv(self, tmp_path):
        _make_project(tmp_path, "alpha")
        # Hidden folder
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "pyproject.toml").write_text("")
        # venv folder
        venv = tmp_path / "venv"
        venv.mkdir()
        (venv / "pyproject.toml").write_text("")

        projects = discover_projects(tmp_path, max_depth=2)
        names = [p.name for p in projects]
        assert "alpha" in names
        assert ".hidden" not in names
        assert "venv" not in names

    def test_does_not_dive_into_project(self, tmp_path):
        """If a folder is a project, don't look inside for more projects."""
        outer = _make_project(tmp_path, "outer")
        inner = _make_project(outer, "inner")

        projects = discover_projects(tmp_path, max_depth=3)
        names = [p.name for p in projects]
        assert "outer" in names
        assert "inner" not in names

    def test_extracts_tasks_and_workflows(self, tmp_path):
        _make_project(
            tmp_path, "alpha",
            tasks=["install", "test", "deploy"],
            workflows=["install", "test"],
        )
        projects = discover_projects(tmp_path, max_depth=1)
        alpha = projects[0]
        assert alpha.taskfile_tasks == ["install", "test", "deploy"]
        assert alpha.doql_workflows == ["install", "test"]


class TestFilterProjects:
    def test_filter_by_task(self, tmp_path):
        _make_project(tmp_path, "alpha", tasks=["install", "test"])
        _make_project(tmp_path, "beta", tasks=["install", "deploy"])
        _make_project(tmp_path, "gamma", tasks=["build"])

        projects = discover_projects(tmp_path, max_depth=1)
        with_test = filter_projects(projects, has_task="test")
        assert [p.name for p in with_test] == ["alpha"]

        with_install = filter_projects(projects, has_task="install")
        assert {p.name for p in with_install} == {"alpha", "beta"}

    def test_filter_by_workflow(self, tmp_path):
        _make_project(tmp_path, "alpha", workflows=["install", "test"])
        _make_project(tmp_path, "beta", workflows=["install"])

        projects = discover_projects(tmp_path, max_depth=1)
        with_test = filter_projects(projects, has_workflow="test")
        assert [p.name for p in with_test] == ["alpha"]

    def test_filter_by_name_pattern(self, tmp_path):
        _make_project(tmp_path, "algitex")
        _make_project(tmp_path, "ats-benchmark")
        _make_project(tmp_path, "clickmd")

        projects = discover_projects(tmp_path, max_depth=1)
        result = filter_projects(projects, name_pattern=r"^a")
        assert {p.name for p in result} == {"algitex", "ats-benchmark"}


class TestValidateProject:
    def test_no_issues(self, tmp_path):
        _make_project(tmp_path, "alpha")
        projects = discover_projects(tmp_path, max_depth=1)
        issues = validate_project(projects[0])
        assert issues == []

    def test_missing_taskfile(self, tmp_path):
        _make_project(tmp_path, "alpha", with_taskfile=False)
        projects = discover_projects(tmp_path, max_depth=1)
        issues = validate_project(projects[0])
        assert any("Missing Taskfile.yml" in i for i in issues)

    def test_empty_workflow_detected(self, tmp_path):
        proj = _make_project(tmp_path, "alpha")
        # Overwrite doql with empty workflow
        (proj / "app.doql.css").write_text(
            'app { name: "x"; version: "0.1.0"; }\n'
            'workflow[name="empty"] { trigger: "manual"; }\n'
        )
        projects = discover_projects(tmp_path, max_depth=1)
        issues = validate_project(projects[0])
        assert any("Empty workflow" in i for i in issues)


class TestCompareProjects:
    def test_empty_input(self):
        assert compare_projects([]) == []

    def test_computes_medians(self, tmp_path):
        _make_project(tmp_path, "a", tasks=["t1", "t2", "t3"])
        _make_project(tmp_path, "b", tasks=["t1", "t2", "t3", "t4", "t5"])
        _make_project(tmp_path, "c", tasks=["t1", "t2", "t3", "t4"])
        projects = discover_projects(tmp_path, max_depth=1)
        reports = compare_projects(projects)
        assert all(r['median_tasks'] == 4 for r in reports)

    def test_identifies_missing_common_tasks(self, tmp_path):
        # Three projects share install/test, only "outlier" is missing test
        _make_project(tmp_path, "a", tasks=["install", "test", "build"])
        _make_project(tmp_path, "b", tasks=["install", "test", "build"])
        _make_project(tmp_path, "c", tasks=["install", "test", "build"])
        _make_project(tmp_path, "outlier", tasks=["install"])

        projects = discover_projects(tmp_path, max_depth=1)
        reports = compare_projects(projects, common_threshold=0.5)
        outlier = next(r for r in reports if r['name'] == 'outlier')
        assert 'test' in outlier['missing_common_tasks']
        assert 'build' in outlier['missing_common_tasks']
        assert 'install' not in outlier['missing_common_tasks']

    def test_mkhint_excluded_when_no_makefile(self, tmp_path):
        # `import-makefile-hint` is common across projects but the outlier
        # has no Makefile — it must NOT be flagged as missing there.
        for name in ("a", "b", "c"):
            p = _make_project(
                tmp_path, name,
                tasks=["install", "test", "import-makefile-hint"],
                workflows=["install", "test", "import-makefile-hint"],
            )
            (p / "Makefile").write_text("all:\n\techo ok\n")
        _make_project(
            tmp_path, "outlier",
            tasks=["install", "test"],
            workflows=["install", "test"],
        )  # no Makefile, no hint task

        projects = discover_projects(tmp_path, max_depth=1)
        reports = compare_projects(projects, common_threshold=0.5)
        outlier = next(r for r in reports if r['name'] == 'outlier')
        assert 'import-makefile-hint' not in outlier['missing_common_tasks']
        assert 'import-makefile-hint' not in outlier['missing_common_workflows']

    def test_mkhint_flagged_when_makefile_present(self, tmp_path):
        # Same setup but outlier HAS a Makefile → hint should be flagged.
        for name in ("a", "b", "c"):
            p = _make_project(
                tmp_path, name,
                tasks=["install", "test", "import-makefile-hint"],
                workflows=["install", "test", "import-makefile-hint"],
            )
            (p / "Makefile").write_text("all:\n\techo ok\n")
        outlier = _make_project(
            tmp_path, "outlier",
            tasks=["install", "test"],
            workflows=["install", "test"],
        )
        (outlier / "Makefile").write_text("all:\n\techo ok\n")

        projects = discover_projects(tmp_path, max_depth=1)
        reports = compare_projects(projects, common_threshold=0.5)
        outlier_r = next(r for r in reports if r['name'] == 'outlier')
        assert 'import-makefile-hint' in outlier_r['missing_common_tasks']

    def test_detects_sync_issues(self, tmp_path):
        # Task in Taskfile but no corresponding workflow in doql
        _make_project(
            tmp_path, "a",
            tasks=["install", "test", "deploy"],
            workflows=["install", "test"],  # deploy missing from doql
        )
        projects = discover_projects(tmp_path, max_depth=1)
        reports = compare_projects(projects)
        assert 'deploy' in reports[0]['tasks_missing_in_doql']

    def test_detects_orphan_workflows(self, tmp_path):
        _make_project(
            tmp_path, "a",
            tasks=["install", "test"],
            workflows=["install", "test", "orphan"],  # orphan has no matching task
        )
        projects = discover_projects(tmp_path, max_depth=1)
        reports = compare_projects(projects)
        assert 'orphan' in reports[0]['orphan_workflows']

    def test_tasks_vs_median(self, tmp_path):
        _make_project(tmp_path, "a", tasks=["t1", "t2", "t3"])
        _make_project(tmp_path, "b", tasks=["t1", "t2", "t3", "t4", "t5", "t6", "t7"])

        projects = discover_projects(tmp_path, max_depth=1)
        reports = compare_projects(projects)
        a_report = next(r for r in reports if r['name'] == 'a')
        b_report = next(r for r in reports if r['name'] == 'b')
        # a has fewer tasks than median, b has more
        assert a_report['tasks_vs_median'] < 0
        assert b_report['tasks_vs_median'] > 0

    def test_has_expected_columns(self, tmp_path):
        _make_project(tmp_path, "a")
        projects = discover_projects(tmp_path, max_depth=1)
        reports = compare_projects(projects)
        required_keys = {
            'path', 'name',
            'taskfile_tasks', 'doql_workflows',
            'median_tasks', 'median_workflows',
            'missing_common_tasks', 'missing_common_workflows',
            'empty_workflows', 'orphan_workflows',
            'tasks_missing_in_doql',
            'issues', 'recommendations',
        }
        assert required_keys <= set(reports[0].keys())
