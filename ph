#!/usr/bin/env sh
# ph — zero-token prompt-history search.
#
# A thin shell shim around ~/.claude/scripts/ph.py so you never type the long
# path. Same engine and flags as the /ph slash command, but it runs entirely in
# your shell — no Claude model turn, no token cost.
#
#   In a terminal:        ph <terms>      e.g.  ph deploy staging --full
#   Inside Claude Code:   !ph <terms>     (the leading ! runs the shell)
#
# Read-only: it only reads ~/.claude/history.jsonl, never writes anything.
exec python3 "${HOME}/.claude/scripts/ph.py" "$@"
