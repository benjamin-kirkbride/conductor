#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BASELINE_FILE="$REPO_ROOT/.meta/flaky_count"
if [[ ! -f "$BASELINE_FILE" ]]; then
    echo "ERROR: Baseline file not found: $BASELINE_FILE"
    exit 1
fi

baseline=$(< "$BASELINE_FILE")
baseline="${baseline%"${baseline##*[![:space:]]}"}"  # trim trailing whitespace

current=$({ grep -rc '@flaky\|@pytest\.mark\.flaky' "$REPO_ROOT/tests/" || true; } | awk -F: '{s+=$2} END {print s+0}')

if [[ "$current" -ne "$baseline" ]]; then
    echo "FLAKY CHECK FAILED"
    echo "  Baseline: $baseline"
    echo "  Current:  $current"
    echo ""
    echo "New flaky markers found:"
    echo ""
    grep -rn '@flaky\|@pytest\.mark\.flaky' "$REPO_ROOT/tests/"
    echo ""
    echo "Review the lines above and remove any unjustified flaky markers."
    exit 1
fi
