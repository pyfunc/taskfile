# Taskfile Examples Test Report

Generated: 2026-04-17

## Summary

| Status | Count |
|--------|-------|
| ✅ Valid | 56 |
| ⚠️ Warnings | 0 |
| ❌ Errors | 0 |
| **Total** | **56** |

Generated with: `taskfile doctor --examples --report`

## All Examples (56/56 passing)

| Example | Tasks | Envs | Status |
|---------|-------|------|--------|
| ai-aider | 13 | ✓ | ✅ |
| ai-claude-code | 17 | ✓ | ✅ |
| ai-codex | 15 | ✓ | ✅ |
| ai-copilot | 17 | ✓ | ✅ |
| ai-cursor | 12 | ✓ | ✅ |
| ai-gemini-cli | 15 | ✓ | ✅ |
| ai-windsurf | 12 | ✓ | ✅ |
| ci-generation | 18 | ✓ | ✅ |
| ci-pipeline | 10 | ✓ | ✅ |
| cloud-aws | 17 | ✓ | ✅ |
| codereview.pl | 17 | ✓ | ✅ |
| edge-iot | 14 | ✓ | ✅ |
| enhanced-error-reporting | 5 | ✓ | ✅ |
| fleet-rpi | 10 | ✓ | ✅ |
| fullstack-deploy | 20 | ✓ | ✅ |
| functions-embed | 9 | ✓ | ✅ |
| iac-ansible | 1 | ✓ | ✅ |
| iac-argocd | 9 | ✓ | ✅ |
| iac-bicep | 9 | ✓ | ✅ |
| iac-cdk-aws | 11 | ✓ | ✅ |
| iac-cdktf | 10 | ✓ | ✅ |
| iac-cloudformation | 9 | ✓ | ✅ |
| iac-crossplane | 8 | ✓ | ✅ |
| iac-docker-compose | 10 | ✓ | ✅ |
| iac-fluxcd | 9 | ✓ | ✅ |
| iac-gcp-deployment-manager | 9 | ✓ | ✅ |
| iac-helm | 2 | ✓ | ✅ |
| iac-kustomize | 9 | ✓ | ✅ |
| iac-nixos | 11 | ✓ | ✅ |
| iac-nomad | 10 | ✓ | ✅ |
| iac-opentofu | 3 | ✓ | ✅ |
| iac-packer | 8 | ✓ | ✅ |
| iac-pulumi | 10 | ✓ | ✅ |
| iac-serverless | 11 | ✓ | ✅ |
| iac-terraform | 14 | ✓ | ✅ |
| iac-terragrunt | 9 | ✓ | ✅ |
| iac-vagrant | 12 | ✓ | ✅ |
| import-cicd | 6 | — | ✅ |
| include-split | 2 | ✓ | ✅ |
| kubernetes-deploy | 17 | ✓ | ✅ |
| mega-saas | 62 | ✓ | ✅ |
| mega-saas-v2 | 27 | ✓ | ✅ |
| minimal | 3 | — | ✅ |
| monorepo-microservices | 24 | ✓ | ✅ |
| multi-artifact | 24 | ✓ | ✅ |
| multiplatform | 20 | ✓ | ✅ |
| publish-cargo | 17 | ✓ | ✅ |
| publish-desktop | 17 | ✓ | ✅ |
| publish-docker | 9 | ✓ | ✅ |
| publish-github | 8 | — | ✅ |
| publish-mobile | 23 | ✓ | ✅ |
| publish-npm | 17 | ✓ | ✅ |
| publish-pypi | 8 | — | ✅ |
| quadlet-podman | 16 | ✓ | ✅ |
| saas-app | 8 | ✓ | ✅ |
| script-extraction | 13 | ✓ | ✅ |

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
