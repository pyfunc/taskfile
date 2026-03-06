# Taskfile Examples Test Report

Generated: 2026-03-06

## Summary

| Status | Count |
|--------|-------|
| ✅ Valid | 17 |
| ⚠️ Warnings (missing .env) | 9 |
| ❌ Errors | 0 |
| **Total** | **26** |

## Valid Examples (No Issues)

| Example | Tasks | Envs | Deps |
|---------|-------|------|------|
| minimal | 3 | 1 | 1 |
| saas-app | 8 | 3 | 1 |
| multiplatform | 20 | 2 | 5 |
| fleet-rpi | 10 | 7 | 0 |
| kubernetes-deploy | 17 | 4 | 3 |
| codereview.pl | 17 | 2 | 2 |
| functions-embed | 9 | 2 | 2 |
| import-cicd | 6 | 1 | 1 |
| include-split | 11 | 3 | 3 |
| multi-artifact | 24 | 2 | 14 |
| publish-docker | 9 | 2 | 4 |
| publish-github | 8 | 1 | 5 |
| publish-pypi | 8 | 1 | 4 |
| script-extraction | 13 | 2 | 1 |

## Examples with Warnings (Missing .env files)

| Example | Tasks | Envs | Missing Files |
|---------|-------|------|---------------|
| ci-pipeline | 10 | 3 | .env.prod |
| fullstack-deploy | 20 | 3 | .env.staging, .env.prod |
| quadlet-podman | 16 | 2 | .env.prod |
| cloud-aws | 17 | 5 | .env.dev, .env.staging, .env.prod-eu, .env.prod-us |
| edge-iot | 14 | 6 | .env.factory, .env.warehouse, .env.office |
| iac-terraform | 14 | 5 | .env.dev, .env.staging, .env.prod, .env.prod-us |
| monorepo-microservices | 24 | 3 | .env.local, .env.staging, .env.prod |
| publish-cargo | 17 | 2 | .env.local, .env.prod |
| publish-desktop | 17 | 2 | .env.local, .env.prod |
| publish-mobile | 23 | 3 | .env.local, .env.staging, .env.prod |
| publish-npm | 17 | 2 | .env.local, .env.prod |

## Notes

- All examples have valid Taskfile.yml syntax
- Warnings are only about missing .env files which are expected in templates
- Users should copy .env.*.example files and customize for their environment
- All examples can be initialized with `taskfile doctor --fix`

## Next Steps

1. Add .env.example files for all examples with missing env files
2. Document the env file requirements in each example's README
3. Consider adding `taskfile init` support for generating env files
