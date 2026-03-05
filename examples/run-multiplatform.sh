#!/bin/bash
# Run multiplatform example - desktop + web × local + prod
set -e

cd "$(dirname "$0")/multiplatform"

echo "═══════════════════════════════════════════════════════════════"
echo "  Multiplatform Example (Desktop + Web)"
echo "═══════════════════════════════════════════════════════════════"

export PYTHONPATH="/home/tom/github/pyfunc/taskfile/src:$PYTHONPATH"

echo ""
echo "▶ taskfile list"
taskfile list 2>/dev/null || python3 -m taskfile list

echo ""
echo "▶ Platforms:"
echo "  - desktop: Electron app"
echo "  - web:     Docker container"

echo ""
echo "▶ Environments:"
echo "  - local: Local development"
echo "  - prod:  Production server"

echo ""
echo "▶ Matrix combinations:"
for env in local prod; do
  for platform in desktop web; do
    echo ""
    echo "  [$env × $platform]"
    taskfile --env $env --platform $platform list 2>/dev/null || \
      python3 -m taskfile --env $env --platform $platform list
  done
done

echo ""
echo "✅ Multiplatform example completed"
