#!/bin/bash
# Run ALL examples in sequence
# NOTE: No 'set -e' - we handle errors manually to track all results

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "═══════════════════════════════════════════════════════════════"
echo "  Taskfile Examples - Complete Test Suite"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "This script runs all examples to verify they work correctly."
echo ""

export PYTHONPATH="/home/tom/github/pyfunc/taskfile/src:$PYTHONPATH"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

run_example() {
    local name=$1
    local script=$2
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Running: $name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if bash "$SCRIPT_DIR/$script"; then
        echo -e "${GREEN}✓ $name: PASSED${NC}"
        return 0
    else
        echo -e "${RED}✗ $name: FAILED${NC}"
        return 1
    fi
}

# Track results
PASSED=0
FAILED=0

# Run each example - don't let one failure stop others
if run_example "minimal" "run-minimal.sh"; then
    ((PASSED++))
else
    ((FAILED++))
fi

if run_example "saas-app" "run-saas-app.sh"; then
    ((PASSED++))
else
    ((FAILED++))
fi

if run_example "multiplatform" "run-multiplatform.sh"; then
    ((PASSED++))
else
    ((FAILED++))
fi

if run_example "codereview.pl" "run-codereview.sh"; then
    ((PASSED++))
else
    ((FAILED++))
fi

if run_example "workspace" "workspace/run.sh"; then
    ((PASSED++))
else
    ((FAILED++))
fi

# Summary
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Summary"
echo "═══════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}Passed: $PASSED${NC}"
echo -e "  ${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All examples completed successfully!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some examples failed${NC}"
    exit 1
fi
