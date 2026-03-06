# Taskfile Examples Test Report

Generated: 2026-03-06 (updated after diagnostics refactoring)

## Summary

| Status | Count |
|--------|-------|
| ✅ Valid | 26 |
| ⚠️ Warnings | 0 |
| ❌ Errors | 0 |
| **Total** | **26** |

Generated with: `taskfile doctor --examples --report`

## All Examples (26/26 passing)

| Example | Tasks | Envs | Status |
|---------|-------|------|--------|
| ci-generation | 18 | 3 | ✅ |
| ci-pipeline | 10 | 3 | ✅ |
| cloud-aws | 17 | 5 | ✅ |
| codereview.pl | 17 | 2 | ✅ |
| edge-iot | 14 | 6 | ✅ |
| fleet-rpi | 10 | 7 | ✅ |
| fullstack-deploy | 20 | 3 | ✅ |
| functions-embed | 9 | 2 | ✅ |
| iac-terraform | 14 | 5 | ✅ |
| import-cicd | 6 | 1 | ✅ |
| include-split | 11 | 3 | ✅ |
| kubernetes-deploy | 17 | 4 | ✅ |
| minimal | 3 | 1 | ✅ |
| monorepo-microservices | 24 | 3 | ✅ |
| multi-artifact | 24 | 2 | ✅ |
| multiplatform | 20 | 2 | ✅ |
| publish-cargo | 17 | 2 | ✅ |
| publish-desktop | 17 | 2 | ✅ |
| publish-docker | 9 | 2 | ✅ |
| publish-github | 8 | 1 | ✅ |
| publish-mobile | 23 | 3 | ✅ |
| publish-npm | 17 | 2 | ✅ |
| publish-pypi | 8 | 1 | ✅ |
| quadlet-podman | 16 | 2 | ✅ |
| saas-app | 8 | 3 | ✅ |
| script-extraction | 13 | 2 | ✅ |

## What Was Fixed

Previously 9 examples had missing `.env` files. All resolved:

- **ci-pipeline** — added `.env.prod` (from `.env.prod.example`)
- **cloud-aws** — added `.env.dev`, `.env.staging`, `.env.prod-eu`, `.env.prod-us` + `.example` templates
- **edge-iot** — added `.env.factory`, `.env.warehouse`, `.env.office` + `.example` templates
- **iac-terraform** — added `.env.prod`, `.env.prod-us` + `.example` template
- **monorepo-microservices** — added `.env.local`, `.env.prod`
- **publish-cargo** — added `.env.local`, `.env.prod`
- **publish-desktop** — added `.env.local`, `.env.prod`
- **publish-mobile** — added `.env.local`, `.env.staging`, `.env.prod`
- **publish-npm** — added `.env.local`, `.env.prod`
- **saas-app** — added `.env.prod`

## Validation Commands

```bash
# Quick check — JSON report for CI
taskfile doctor --examples --report

# Interactive check with categorized output
taskfile doctor --examples

# Auto-fix missing .env files (copies from .example)
taskfile doctor --fix
```

## Notes

- All examples have valid Taskfile.yml syntax
- Every environment's `env_file` reference has a corresponding file and `.example` template
- Users should copy `.env.*.example` files and customize for their environment
- Run `taskfile doctor --fix` in any example directory for interactive setup
