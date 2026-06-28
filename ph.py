#!/usr/bin/env python3
"""Search the full Claude Code prompt history (~/.claude/history.jsonl).

The in-session Ctrl+R picker only loads the 100 most recent unique prompts
(official, documented, not configurable). This scans EVERY entry across all
projects and all time — the only full-history search Claude Code has.

Usage:
  ph.py TERM [TERM ...]          all terms must match (AND), case-insensitive
  ph.py --regex "PATTERN"        treat the query as one regex
  ph.py --project asr-eval cfg   restrict to projects whose path contains "asr-eval"
  ph.py --days 60 deploy         only the last 60 days
  ph.py --limit 80 train         show up to 80 matches (default 30)
  ph.py --full token             show full prompt text (no truncation)
  ph.py --oldest setup           oldest matches first (default: newest first)
  ph.py --copy 3 token           print ONLY match #3's full text (clean to copy/rerun)
  ph.py --projects               list every project with history + counts/date span
"""
import sys, os, json, re, argparse, datetime

HIST = os.path.expanduser("~/.claude/history.jsonl")
TRUNC = 280


def load():
    rows = []
    try:
        with open(HIST) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if "timestamp" in r and "display" in r:
                        rows.append(r)
                except Exception:
                    pass
    except FileNotFoundError:
        sys.exit(f"history file not found: {HIST}")
    rows.sort(key=lambda r: r["timestamp"], reverse=True)  # newest first
    return rows


def when(ts):
    v = ts / 1000 if ts > 1e11 else ts
    return datetime.datetime.fromtimestamp(v)


def rel(dt, now):
    days = (now.date() - dt.date()).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days}d ago"
    if days < 60:
        return f"{days // 7}w ago"
    return f"{days // 30}mo ago"


def highlight(text, terms):
    for t in terms:
        if not t:
            continue
        text = re.sub("(" + re.escape(t) + ")", r"**\1**", text, flags=re.I)
    return text


def projects_overview(rows):
    from collections import defaultdict
    byp = defaultdict(list)
    for r in rows:
        byp[r.get("project", "?")].append(when(r["timestamp"]))
    print(f"prompt-history: {len(byp)} projects, {len(rows)} total prompts\n")
    for p, ts in sorted(byp.items(), key=lambda kv: -len(kv[1])):
        ts.sort()
        name = os.path.basename(p) or p
        print(f"  {len(ts):5d}  {ts[0].date()} -> {ts[-1].date()}  {name}")
    print("\nTip: /ph --project NAME <terms>  to search inside one project.")


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("terms", nargs="*", help="search terms (AND, case-insensitive)")
    ap.add_argument("--regex", help="single regex pattern (overrides terms)")
    ap.add_argument("--project", help="only projects whose path contains this substring")
    ap.add_argument("--days", type=int, help="only entries within the last N days")
    ap.add_argument("--limit", type=int, default=30, help="max matches to show (default 30)")
    ap.add_argument("--full", action="store_true", help="show full prompt text (no truncation)")
    ap.add_argument("--oldest", action="store_true", help="oldest matches first")
    ap.add_argument("--copy", type=int, metavar="N", help="print only match N's full text")
    ap.add_argument("--projects", action="store_true", help="list projects with history")
    args = ap.parse_args()

    rows = load()
    total = len(rows)
    now = when(rows[0]["timestamp"]) if rows else datetime.datetime.now()

    if args.projects:
        projects_overview(rows)
        return

    if args.days:
        cut = now - datetime.timedelta(days=args.days)
        rows = [r for r in rows if when(r["timestamp"]) >= cut]
    if args.project:
        p = args.project.lower()
        rows = [r for r in rows if p in (r.get("project", "")).lower()]

    if args.regex:
        rx = re.compile(args.regex, re.I)
        match, terms = (lambda d: rx.search(d)), []
    elif args.terms:
        terms = args.terms
        low = [t.lower() for t in terms]
        match, terms = (lambda d: all(t in d.lower() for t in low)), terms
    else:
        match, terms = None, []

    # dedup identical prompts, keep newest, count repeats
    seen, hits = {}, []
    for r in rows:
        if match is not None and not match(r["display"]):
            continue
        key = r["display"].strip()
        if key in seen:
            seen[key]["_n"] += 1
            continue
        r = dict(r, _n=1)
        seen[key] = r
        hits.append(r)

    if args.oldest:
        hits = hits[::-1]

    # --copy: dump one entry raw and stop
    if args.copy is not None:
        if 1 <= args.copy <= len(hits):
            print(hits[args.copy - 1]["display"])
        else:
            print(f"(no match #{args.copy}; there are {len(hits)})")
        return

    shown = hits[: args.limit]
    q = args.regex or (" ".join(terms) if terms else "(recent, all projects)")

    if not hits:
        print(f"prompt-history: no match for {q!r} (scanned {total} prompts).")
        print("Try fewer/shorter terms, drop --project/--days, or `/ph --projects` to see what's there.")
        return

    print(f"prompt-history: {len(hits)} unique match for {q!r}  "
          f"(scanned {total} prompts, showing {len(shown)})\n")
    for i, r in enumerate(shown, 1):
        dt = when(r["timestamp"])
        stamp = dt.strftime("%b %d %H:%M")
        proj = os.path.basename(r.get("project", "") or "?")
        reps = f"  ×{r['_n']}" if r["_n"] > 1 else ""
        text = " ".join(r["display"].split())
        if not args.full and len(text) > TRUNC:
            text = text[: TRUNC - 3] + "..."
        if terms:
            text = highlight(text, terms)
        print(f"[{i}] {stamp} · {rel(dt, now):>9}  ({proj}){reps}\n    {text}\n")
    if len(hits) > len(shown):
        print(f"... {len(hits) - len(shown)} more — add a term to narrow or raise --limit.")
    print("Reply with a number to rerun that prompt, or `--full` / `--copy N` for complete text.")


if __name__ == "__main__":
    main()
