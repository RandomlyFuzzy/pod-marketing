#!/bin/bash
# Meta test script for the agent system architecture
# Runs a series of tests to validate core mechanisms

set -e  # Exit on any error

# Project root
PROJECT_ROOT="/home/rf/Documents/pod_marketing"
cd "$PROJECT_ROOT"

# Activate virtual environment
source mcp_server/venv/bin/activate

echo "=== Agent System Meta Test Suite ==="
echo "Testing core architecture mechanisms..."
echo ""

# Test counter
PASSED=0
FAILED=0
TOTAL_TESTS=0

# Helper function to run a test and evaluate result
run_test() {
    local test_name="$1"
    local command="$2"
    local check_function="$3"
    local timeout_sec="${4:-15}"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -n "Test $TOTAL_TESTS: $test_name ... "
    
    # Run command with timeout
    local output
    output=$(timeout "$timeout_sec" bash -c "$command" 2>&1)
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        echo "FAILED (command timed out or exited with error)"
        echo "Output: $output"
        FAILED=$((FAILED + 1))
        return
    fi
    
    # Apply check function
    if eval "$check_function" "$output"; then
        echo "PASSED"
        PASSED=$((PASSED + 1))
    else
        echo "FAILED (check condition not met)"
        echo "Output: $output"
        FAILED=$((FAILED + 1))
    fi
}

# Test 1: CLI list should expose the live team manifest
run_test "Team Manifest" \
    "python -m agent_system.cli list 2>&1" \
    '[[ "$1" =~ "Registered team/agent capabilities" ]] && [[ "$1" =~ "researcher" ]] && [[ "$1" =~ "MCP tools" ]]' \
    10

# Test 2: Legacy direct-agent shape must route through orchestrator
run_test "Legacy General Routes Through Orchestrator" \
    "timeout 15 python -m agent_system.cli general researcher 'Say ping and stop.' 2>&1" \
    '[[ "$1" =~ "ORCHESTRATOR" ]]' \
    20

# Test 3: Legacy planner shape must route through orchestrator
run_test "Legacy Planner Routes Through Orchestrator" \
    "timeout 15 python -m agent_system.cli planner 'Say ping and stop.' 2>&1" \
    '[[ "$1" =~ "ORCHESTRATOR" ]]' \
    20

# Test 4: Orchestrator remains the canonical execution mode
run_test "Orchestrator Mode" \
    "timeout 15 python -m agent_system.cli orchestrator 'Say ping and stop.' 2>&1" \
    '[[ "$1" =~ "ORCHESTRATOR" ]]' \
    20

# Test 5: Max iteration default is bounded in source
run_test "Max Iteration Default" \
    "python - <<'PY'\nimport inspect\nfrom agent_system.orchestrator_agent import run_orchestrator\nprint(inspect.signature(run_orchestrator))\nPY" \
    '[[ "$1" =~ "max_iterations: int = 5" ]]' \
    10

# Summary
echo ""
echo "=== Test Summary ==="
echo "Total tests: $TOTAL_TESTS"
echo "Passed: $PASSED"
echo "Failed: $FAILED"

if [ $FAILED -eq 0 ]; then
    echo "🎉 All meta tests passed! Agent system architecture is functioning correctly."
    exit 0
else
    echo "⚠️  Some tests failed. Review output above for details."
    exit 1
fi
