#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BASELINE_FILE="$REPO_ROOT/.meta/pragma_no_count"
if [[ ! -f "$BASELINE_FILE" ]]; then
    echo "ERROR: Baseline file not found: $BASELINE_FILE"
    exit 1
fi

baseline=$(< "$BASELINE_FILE")
baseline="${baseline%"${baseline##*[![:space:]]}"}"  # trim trailing whitespace

current=$({ grep -rc "# pragma: no " "$REPO_ROOT/src/" || true; } | awk -F: '{s+=$2} END {print s+0}')

if [[ "$current" -ne "$baseline" ]]; then
    echo "PRAGMA CHECK FAILED"
    echo "  Baseline: $baseline"
    echo "  Current:  $current"
    echo ""
    echo "New '# pragma: no *' comments found:"
    echo ""
    grep -rn "# pragma: no " "$REPO_ROOT/src/"
    echo ""
    echo "Review the lines above and remove any unjustified pragmas."
    exit 1
fi
