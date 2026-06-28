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
[ "$out" = "deploy the staging environment and check health" ]; pass "--copy by row number prints raw prompt"

# --- stable ids ---
# The id is a content hash, so it must be identical no matter the query that
# surfaced the prompt — that's what makes --copy <id> drift-proof.
ID=$(run --json deploy staging | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
[ -n "$ID" ]; pass "results carry a stable id (json)"
ID2=$(run --json --no-dedup deploy | python3 -c 'import sys,json; rows=json.load(sys.stdin); print(next(r["id"] for r in rows if r["display"].startswith("deploy the staging")))')
[ "$ID" = "$ID2" ]; pass "id is stable across different queries"
[ "$(run --copy "$ID" deploy staging)" = "deploy the staging environment and check health" ]; pass "--copy by id resolves the prompt"
[ "$(run --show "$ID" deploy staging)" = "deploy the staging environment and check health" ]; pass "--show is an alias of --copy"
run --copy zzzzzzz deploy staging | grep -q "no match"; pass "--copy with unknown id reports no match"

# --- --clip degrades gracefully when no clipboard tool is usable ---
clip_out=$(run --copy 1 deploy staging --clip 2>/dev/null)
[ "$clip_out" = "deploy the staging environment and check health" ]; pass "--clip still prints the prompt (graceful fallback)"

# --- copy/show subcommand sugar (no leading --) ---
[ "$(run copy 1 deploy staging)" = "deploy the staging environment and check health" ]; pass "copy-N subcommand works without --"
[ "$(run copy 1)" = "deploy the staging environment and check health" ]; pass "copy-N subcommand needs no query"
[ "$(run show "$ID" deploy staging)" = "deploy the staging environment and check health" ]; pass "show-ID subcommand works without --"
run copy paste | grep -q "no match"; pass "copy <non-id> stays a normal search (not hijacked)"

# --- interactive mode: must NOT engage when stdout is not a TTY (piped here) ---
run -i deploy staging | grep -q "unique match"; pass "-i is bypassed when stdout is not a TTY"
run | grep -q "Reply with a number"; pass "bare run (no TTY) keeps the non-interactive listing"

run --projects | grep -q "web-dashboard"; pass "--projects lists projects"
run zzzznope | grep -q "no match"; pass "empty-state on no match"
run --regex "deploy|tests" | grep -q "unique match"; pass "--regex search"

# --- new flags ---
count_json() { python3 -c 'import sys,json; print(len(json.load(sys.stdin)))'; }
run --json deploy staging | python3 -c 'import sys,json; assert isinstance(json.load(sys.stdin), list)'; pass "--json emits a JSON array"
[ "$(run --json deploy staging | count_json)" = "2" ]; pass "--json respects dedup (2 unique)"
[ "$(run --no-dedup --json deploy staging | count_json)" = "3" ]; pass "--no-dedup keeps duplicates (3)"
[ "$(run --since 2099-01-01 --json deploy staging | count_json)" = "0" ]; pass "--since filters out older entries"
[ "$(run --until 2000-01-01 --json deploy staging | count_json)" = "0" ]; pass "--until filters out newer entries"
run --since notadate deploy 2>&1 | grep -q "invalid date"; pass "--since rejects a bad date"

# --- --width: per-result truncation budget ---
run --width 12 deploy staging | grep -q '\.\.\.'; pass "--width truncates to a smaller budget"
if run --width 12 deploy staging | grep -q "check health"; then echo "FAIL: --width did not truncate"; exit 1; fi
pass "--width hides text beyond the budget"
run --full deploy staging | grep -q "check health"; pass "--full shows the complete prompt"
# /ph injects a lean default width; a later --width from the user must override
# it (argparse last-wins). These guard that contract.
if run --width 12 --width 400 deploy staging | grep -q '\.\.\.'; then echo "FAIL: later --width did not win"; exit 1; fi
pass "a later --width overrides an earlier one (last-wins)"
run --width 400 --width 12 deploy staging | grep -q '\.\.\.'; pass "earlier --width is overridden by a later smaller one"

# --- ph shell wrapper (zero-token shim) ---
sh -n "$HERE/ph"; pass "ph wrapper: valid shell syntax"
[ -x "$HERE/ph" ]; pass "ph wrapper: executable bit set"
# End-to-end: the wrapper must exec ph.py from $HOME/.claude/scripts and pass
# args straight through. Stage a copy under the isolated HOME and invoke it.
mkdir -p "$TMP/.claude/scripts"
cp "$HERE/ph.py" "$TMP/.claude/scripts/ph.py"
wrap=$(HOME="$TMP" sh "$HERE/ph" --copy 1 deploy staging)
[ "$wrap" = "deploy the staging environment and check health" ]; pass "ph wrapper: passes args through to ph.py"

# --- interactive-mode logic (pure functions; curses UI itself needs a pty) ---
python3 "$HERE/tests/test_logic.py"; pass "interactive-mode logic unit tests"

echo "ALL SMOKE TESTS PASSED"
