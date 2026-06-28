#!/usr/bin/env sh
# Smoke test for ph.py against a synthetic history file in an isolated HOME.
# Run locally with:  sh tests/smoke.sh
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude"

# Synthetic history — NOT real prompts. Two identical lines exercise dedup.
cat > "$TMP/.claude/history.jsonl" <<'JSON'
{"display":"deploy the staging environment and check health","timestamp":1781990000000,"project":"/home/u/web-dashboard","sessionId":"a"}
{"display":"deploy the staging environment and check health","timestamp":1781990500000,"project":"/home/u/web-dashboard","sessionId":"b"}
{"display":"write a github actions deploy-to-staging job","timestamp":1781000000000,"project":"/home/u/billing-api","sessionId":"c"}
{"display":"fix the failing unit tests in data-pipeline","timestamp":1780000000000,"project":"/home/u/data-pipeline","sessionId":"d"}
JSON

run() { HOME="$TMP" python3 "$HERE/ph.py" "$@"; }
pass() { echo "  ok: $1"; }
# Build the U+00D7 ("x N" repeat marker) via Python — portable across sh/dash,
# whose printf does not support \xHH hex escapes.
TIMES=$(python3 -c 'import sys; sys.stdout.write("×")')

# Two identical lines collapse to one, plus the deploy-to-staging line = 2 unique.
run deploy staging | grep -q "2 unique match for 'deploy staging'"; pass "dedup -> 2 unique matches"
run deploy staging | grep -q "${TIMES}2"; pass "repeat marker shows x2"

out=$(run --copy 1 deploy staging)
[ "$out" = "deploy the staging environment and check health" ]; pass "--copy prints raw single prompt"

run --projects | grep -q "web-dashboard"; pass "--projects lists projects"
run zzzznope | grep -q "no match"; pass "empty-state on no match"
run --regex "deploy|tests" | grep -q "unique match"; pass "--regex search"

echo "ALL SMOKE TESTS PASSED"
