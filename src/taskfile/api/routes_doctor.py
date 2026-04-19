"""Doctor diagnostics endpoints for the Taskfile REST API."""

from __future__ import annotations

from fastapi import FastAPI, Query

from taskfile.api.models import (
    DoctorIssueInfo,
    DoctorRequest,
    DoctorResponse,
)


# ── Category filter for doctor endpoint ──────────────────────────

_CATEGORY_FILTER = {
    "config": {"config_error", "taskfile_bug"},
    "env": {"dependency_missing"},
    "infra": {"external_error"},
    "runtime": {"runtime_error"},
}


def register_doctor_routes(app: FastAPI) -> None:
    """Register /doctor diagnostics endpoint."""

    @app.get(
        "/doctor",
        response_model=DoctorResponse,
        tags=["diagnostics"],
        summary="Run doctor diagnostics (GET — read-only)",
    )
    def doctor_get(
        verbose: bool = Query(
            False, description="Run extra checks (task commands, SSH, remote health)"
        ),
        category: str = Query("all", description="Filter: config, env, infra, runtime, or all"),
    ):
        """Run 5-layer diagnostics (read-only, no fixes applied).

        Same as `taskfile doctor --report` but over HTTP.
        """
        return _run_doctor(app, fix=False, verbose=verbose, category=category, llm=False)

    @app.post(
        "/doctor",
        response_model=DoctorResponse,
        tags=["diagnostics"],
        summary="Run doctor diagnostics with options",
    )
    def doctor_post(request: DoctorRequest):
        """Run 5-layer diagnostics with optional auto-fix and LLM assist.

        - **fix**: Apply Layer 4 algorithmic fixes
        - **verbose**: Extra checks (task commands, SSH connectivity, remote health)
        - **llm**: Ask AI for suggestions on unresolved issues (Layer 5)
        - **category**: Filter by issue category
        """
        return _run_doctor(
            app,
            fix=request.fix,
            verbose=request.verbose,
            category=request.category,
            llm=request.llm,
        )


def _run_doctor(
    app: FastAPI,
    *,
    fix: bool = False,
    verbose: bool = False,
    category: str = "all",
    llm: bool = False,
) -> DoctorResponse:
    """Shared doctor logic for GET and POST endpoints."""
    from taskfile.diagnostics import ProjectDiagnostics

    diagnostics = ProjectDiagnostics()
    diagnostics.run_all_checks(verbose=verbose)

    fixed_count = _apply_layer4_fixes(diagnostics, fix)
    llm_suggestions = _apply_layer5_llm(diagnostics, llm)
    issues = _filter_issues_by_category(diagnostics._issues, category)
    issue_infos, by_category = _build_issue_infos(issues)

    return _build_doctor_response(issue_infos, by_category, fixed_count, llm_suggestions)


def _apply_layer4_fixes(diagnostics, fix: bool) -> int:
    """Layer 4: Apply auto-fixes if requested. Returns fixed count."""
    if fix and diagnostics.issues:
        return diagnostics.auto_fix()
    return 0


def _apply_layer5_llm(diagnostics, llm: bool) -> list[str]:
    """Layer 5: Ask LLM for suggestions on unresolved issues."""
    if llm and diagnostics._issues:
        try:
            return diagnostics.llm_repair()
        except Exception:
            pass
    return []


def _filter_issues_by_category(issues, category: str):
    """Filter issues by doctor category (config/env/infra/runtime/all)."""
    if category == "all" or category not in _CATEGORY_FILTER:
        return issues
    allowed = _CATEGORY_FILTER[category]
    return [i for i in issues if i.category.value in allowed]


def _build_issue_infos(issues) -> tuple[list[DoctorIssueInfo], dict[str, list[DoctorIssueInfo]]]:
    """Convert Issue objects to API response models, grouped by category."""
    infos: list[DoctorIssueInfo] = []
    by_category: dict[str, list[DoctorIssueInfo]] = {}
    for iss in issues:
        info = DoctorIssueInfo(
            category=iss.category.value,
            message=iss.message,
            severity=iss.severity,
            fix_strategy=iss.fix_strategy.value,
            auto_fixable=iss.auto_fixable,
            layer=iss.layer,
            fix_command=iss.fix_command,
            fix_description=iss.fix_description,
            teach=iss.teach,
            context={k: v for k, v in iss.context.items() if not k.startswith("_")}
            if iss.context
            else None,
        )
        infos.append(info)
        by_category.setdefault(iss.category.value, []).append(info)
    return infos, by_category


def _build_doctor_response(
    issue_infos: list[DoctorIssueInfo],
    categories: dict[str, list[DoctorIssueInfo]],
    fixed_count: int,
    llm_suggestions: list[str],
) -> DoctorResponse:
    """Assemble the final DoctorResponse from computed parts."""
    error_count = sum(1 for i in issue_infos if i.severity == "error")
    warn_count = sum(1 for i in issue_infos if i.severity == "warning")
    info_count = sum(1 for i in issue_infos if i.severity == "info")
    fixable = sum(1 for i in issue_infos if i.auto_fixable)

    parts = []
    if error_count:
        parts.append(f"Errors: {error_count}")
    if warn_count:
        parts.append(f"Warnings: {warn_count}")
    if info_count:
        parts.append(f"Info: {info_count}")
    if fixed_count:
        parts.append(f"Fixed: {fixed_count}")
    summary = ", ".join(parts) if parts else "No issues found"

    return DoctorResponse(
        total_issues=len(issue_infos),
        errors=error_count,
        warnings=warn_count,
        info=info_count,
        auto_fixable=fixable,
        fixed_count=fixed_count,
        healthy=error_count == 0,
        issues=issue_infos,
        categories=categories,
        llm_suggestions=llm_suggestions,
        summary=summary,
    )
