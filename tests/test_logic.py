#!/usr/bin/env python3
"""Unit tests for ph.py's interactive-mode logic — pure functions, no curses,
no pytest. Run:  python3 tests/test_logic.py  (also invoked by tests/smoke.sh)."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ph  # noqa: E402

n = 0


def check(cond, label):
    global n
    assert cond, f"FAIL: {label}"
    n += 1


def args(**kw):
    base = dict(copy=None, json=False, projects=False, clip=False,
                interactive=False, terms=[], regex=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


# --- should_interactive: activation truth table ---
check(ph.should_interactive(args(), True) is True, "bare + TTY -> interactive")
check(ph.should_interactive(args(), False) is False, "not a TTY -> non-interactive")
check(ph.should_interactive(args(terms=["x"]), True) is False, "query present -> non-interactive")
check(ph.should_interactive(args(regex="x"), True) is False, "regex -> non-interactive")
check(ph.should_interactive(args(copy="1"), True) is False, "--copy -> non-interactive")
check(ph.should_interactive(args(json=True), True) is False, "--json -> non-interactive")
check(ph.should_interactive(args(projects=True), True) is False, "--projects -> non-interactive")
check(ph.should_interactive(args(clip=True), True) is False, "--clip -> non-interactive")
check(ph.should_interactive(args(interactive=True), True) is True, "-i + TTY -> interactive")
check(ph.should_interactive(args(interactive=True, terms=["x"]), True) is True,
      "-i with query -> interactive")
check(ph.should_interactive(args(interactive=True), False) is False,
      "-i but not a TTY -> non-interactive (TTY rule wins)")
check(ph.should_interactive(args(interactive=True, copy="1"), True) is False,
      "result flag overrides -i")

# --- fuzzy_score ---
check(ph.fuzzy_score("", "anything") == 0, "empty query scores 0")
check(ph.fuzzy_score("xyz", "abc") is None, "non-subsequence -> None")
check(ph.fuzzy_score("abc", "abc") is not None, "subsequence matches")
check(ph.fuzzy_score("ABC", "abc") is not None, "case-insensitive")
check(ph.fuzzy_score("rel", "release") is not None, "prefix subsequence matches")
check(ph.fuzzy_score("abc", "abcdef") > ph.fuzzy_score("abc", "a_b_c"),
      "contiguous beats scattered")
check(ph.fuzzy_score("rel", "release now") > ph.fuzzy_score("rel", "the release"),
      "earlier match beats later")

# --- collect_hits: dedup, count, order, filters (the shared core) ---
rows = [
    {"display": "deploy staging", "timestamp": 300, "project": "/u/web"},
    {"display": "deploy staging", "timestamp": 200, "project": "/u/web"},
    {"display": "fix the tests", "timestamp": 100, "project": "/u/api"},
]
anchor = ph.when(300)
hits = ph.collect_hits(rows, now=anchor)
check(len(hits) == 2, "dedup collapses identical prompts to 2")
check(hits[0]["display"] == "deploy staging" and hits[0]["_n"] == 2, "newest kept, x2 counted")
check(hits[0]["timestamp"] == 300, "dedup keeps the newest occurrence")
check(len(ph.collect_hits(rows, no_dedup=True, now=anchor)) == 3, "--no-dedup keeps all 3")
check(len(ph.collect_hits(rows, project="api", now=anchor)) == 1, "project filter")
check(len(ph.collect_hits(rows, terms=["deploy"], now=anchor)) == 1, "terms filter (AND)")
check(ph.collect_hits(rows, oldest=True, now=anchor)[0]["display"] == "fix the tests",
      "oldest reverses order")
check(ph.pid(hits[0]["display"]) == ph.pid("deploy staging"), "pid is content-addressed")

print(f"test_logic: all {n} assertions passed")
