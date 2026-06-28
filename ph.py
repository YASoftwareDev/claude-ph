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
  ph.py --since 2026-01-01 x     only entries on/after a date (YYYY-MM-DD)
  ph.py --until 2026-03-31 x     only entries on/before a date (YYYY-MM-DD)
  ph.py --limit 80 train         show up to 80 matches (default 30)
  ph.py --full token             show full prompt text (no truncation)
  ph.py --width 600 token        show up to 600 chars per result (default 840)
  ph.py --oldest setup           oldest matches first (default: newest first)
  ph.py --no-dedup token         show every occurrence (do not collapse duplicates)
  ph.py --copy 3 token           print ONLY match #3's full text (clean to copy/rerun)
  ph.py --copy a3f2c9 token      print the match with that stable id (drift-proof)
  ph.py copy a3f2c9              subcommand sugar for --copy (also: show)
  ph.py --copy 3 token --clip    copy that prompt straight to the system clipboard
  ph.py --json token             output matches as JSON (for scripts/piping)
  ph.py --projects               list every project with history + counts/date span
  ph.py -i / --interactive       launch the fuzzy picker (also auto-launches on a
                                 bare `ph` in a terminal); piping/flags bypass it

Each result carries a short stable id (a hash of the prompt text). Unlike the
row number, the id never changes as history grows, so `--copy <id>` always
returns the same prompt. `--show` is an alias for `--copy`.
"""
import sys, os, json, re, argparse, datetime, hashlib

HIST = os.path.expanduser("~/.claude/history.jsonl")
TRUNC = 840  # default per-result character budget before truncation (override with --width)


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


def pid(display):
    """Short stable id for a prompt, derived from its text.

    Content-addressed on purpose: it is invariant across repeats, dedup, and
    new history, so `--copy <id>` always resolves to the same prompt — unlike a
    row number, which shifts as prompts are added.
    """
    return hashlib.sha1(display.strip().encode("utf-8")).hexdigest()[:7]


def to_clipboard(text):
    """Best-effort copy to the system clipboard. Returns the tool used, or None.

    Stdlib only. Tries, in order: a native clipboard CLI (needs a local
    display/session) → tmux's buffer (works headless/over SSH; with
    set-clipboard on, tmux also forwards to the outer clipboard) → an OSC 52
    terminal escape (routes the copy to your local machine's clipboard over
    SSH/containers, if the terminal allows it). Returns the mechanism, or None.
    """
    import shutil, subprocess
    for cmd in (["wl-copy"], ["pbcopy"], ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"], ["clip.exe"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode("utf-8"), check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return cmd[0]
            except Exception:
                continue
    if os.environ.get("TMUX") and shutil.which("tmux"):
        for tmux_cmd in (["tmux", "load-buffer", "-w", "-"],  # -w also forwards to the outer clipboard
                         ["tmux", "load-buffer", "-"]):       # older tmux: buffer only (cfv can pull it)
            try:
                subprocess.run(tmux_cmd, input=text.encode("utf-8"), check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return "tmux"
            except Exception:
                continue
    if _osc52(text):
        return "osc52"
    return None


def osc52_sequence(text):
    """Build the OSC 52 'set clipboard' escape for `text` (base64-encoded)."""
    import base64
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"\033]52;c;{b64}\a"


def _osc52(text):
    """Write the OSC 52 escape to the controlling terminal. Returns success.

    The terminal (and tmux, if any) must permit OSC 52; we can't detect that, so
    this is best-effort — callers fall back to printing the prompt instead.
    """
    try:
        with open("/dev/tty", "w") as tty:
            tty.write(osc52_sequence(text))
            tty.flush()
        return True
    except Exception:
        return False


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


def parse_date(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        sys.exit(f"invalid date {s!r} — use YYYY-MM-DD")


def collect_hits(rows, *, terms=None, regex=None, project=None, days=None,
                 since=None, until=None, no_dedup=False, oldest=False, now=None):
    """Filter + dedup + order — the single source of truth for both the CLI and
    the interactive picker (which layers fuzzy matching on top, never forking
    this logic). `since`/`until` are datetimes (`until` exclusive); `now` anchors
    `--days`. Each returned hit carries `_n` (repeat count). Read-only."""
    if now is None:
        now = when(rows[0]["timestamp"]) if rows else datetime.datetime.now()
    out = rows
    if days:
        cut = now - datetime.timedelta(days=days)
        out = [r for r in out if when(r["timestamp"]) >= cut]
    if since:
        out = [r for r in out if when(r["timestamp"]) >= since]
    if until:
        out = [r for r in out if when(r["timestamp"]) < until]
    if project:
        p = project.lower()
        out = [r for r in out if p in (r.get("project", "")).lower()]

    if regex:
        rx = re.compile(regex, re.I)
        match = lambda d: rx.search(d)
    elif terms:
        low = [t.lower() for t in terms]
        match = lambda d: all(t in d.lower() for t in low)
    else:
        match = None

    seen, hits = {}, []
    for r in out:
        if match is not None and not match(r["display"]):
            continue
        key = r["display"].strip()
        if not no_dedup and key in seen:
            seen[key]["_n"] += 1
            continue
        r = dict(r, _n=1)
        if not no_dedup:
            seen[key] = r
        hits.append(r)
    if oldest:
        hits = hits[::-1]
    return hits


def fuzzy_score(query, text):
    """Case-insensitive subsequence score; higher is better, None if no match.
    Rewards compact, early matches (a contiguous substring scores highest) so the
    picker can rank by match quality, then recency."""
    if not query:
        return 0
    q, t = query.lower(), text.lower()
    first = t.find(q[0])
    if first == -1:
        return None
    last, gaps = first, 0
    for ch in q[1:]:
        nxt = t.find(ch, last + 1)
        if nxt == -1:
            return None
        if nxt > last + 1:
            gaps += nxt - last - 1
        last = nxt
    span = last - first + 1
    return -(span + 2 * gaps + first)


def should_interactive(args, stdout_isatty):
    """Decide whether to launch the interactive picker. Pure / unit-tested.
    Result flags and a non-TTY stdout always force the non-interactive path."""
    if args.copy is not None or args.json or args.projects or args.clip:
        return False
    if not stdout_isatty:
        return False
    if getattr(args, "interactive", False):
        return True
    return not args.terms and not args.regex


# ---------------------------------------------------------------------------
# Interactive curses picker (stdlib only; activated per should_interactive()).
# ---------------------------------------------------------------------------

def _addstr(stdscr, y, x, text, w, attr=0):
    import curses
    try:
        stdscr.addnstr(y, x, text, max(0, w - x), attr)
    except curses.error:
        pass


def _status_tags(state, n_filtered, n_base):
    tags = [f"{n_filtered}/{n_base}"]
    if state["project"]:
        tags.append(f"[proj:{state['project']}]")
    if state["days"]:
        tags.append(f"[≤{state['days']}d]")
    if state["since_str"]:
        tags.append(f"[≥{state['since_str']}]")
    if state["until_str"]:
        tags.append(f"[≤{state['until_str']}]")
    tags.append("[dedup:off]" if state["no_dedup"] else "[dedup:on]")
    tags.append("[order:old]" if state["oldest"] else "[order:new]")
    return "  ".join(tags)


def _ask(stdscr, y, label, w):
    """Inline mini-prompt at row y; returns the typed string, or None on Esc."""
    import curses
    curses.curs_set(1)
    buf = ""
    while True:
        stdscr.move(y, 0)
        stdscr.clrtoeol()
        _addstr(stdscr, y, 0, label + buf, w, curses.A_BOLD)
        ch = stdscr.getch()
        if ch in (curses.KEY_ENTER, 10, 13):
            curses.curs_set(0)
            return buf
        if ch == 27:
            curses.curs_set(0)
            return None
        if ch in (curses.KEY_BACKSPACE, 127, 8):
            buf = buf[:-1]
        elif 32 <= ch <= 126:
            buf += chr(ch)


def _viewer(stdscr, header, text):
    """Full-screen scrollable view of one prompt's untruncated text."""
    import curses, textwrap
    while True:
        h, w = stdscr.getmaxyx()
        lines = []
        for para in text.split("\n"):
            lines.extend(textwrap.wrap(para, max(1, w - 1)) or [""])
        page = max(1, h - 2)
        off = 0
        max_off = max(0, len(lines) - page)
        while True:
            stdscr.erase()
            _addstr(stdscr, 0, 0, header, w, curses.A_BOLD)
            for i in range(page):
                if off + i < len(lines):
                    _addstr(stdscr, 1 + i, 0, lines[off + i], w)
            _addstr(stdscr, h - 1, 0, "↑↓/PgUp/PgDn scroll · esc/q back",
                    w, curses.A_REVERSE)
            stdscr.refresh()
            ch = stdscr.getch()
            if ch in (27, ord("q")):
                return
            if ch == curses.KEY_RESIZE:
                break
            if ch in (curses.KEY_DOWN, 14):
                off = min(max_off, off + 1)
            elif ch in (curses.KEY_UP, 16):
                off = max(0, off - 1)
            elif ch == curses.KEY_NPAGE:
                off = min(max_off, off + page)
            elif ch == curses.KEY_PPAGE:
                off = max(0, off - page)


def _tui(stdscr, rows, now, state):
    import curses, textwrap
    curses.curs_set(0)
    stdscr.keypad(True)
    try:
        curses.use_default_colors()
    except curses.error:
        pass

    def base_hits():
        return collect_hits(rows, project=state["project"], days=state["days"],
                            since=state["since"], until=state["until"],
                            no_dedup=state["no_dedup"], oldest=state["oldest"], now=now)

    def apply(base, query):
        if not query:
            return list(base)
        scored = []
        for hh in base:
            s = fuzzy_score(query, hh["display"])
            if s is not None:
                scored.append((s, hh["timestamp"], hh))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [hh for _, _, hh in scored]

    base = base_hits()
    query = state["query"]
    filtered = apply(base, query)
    sel, flash = 0, ""
    legend = ("↑↓ move · ⏎ print · ^Y copy · ^B id · "
              "^V view · ^G proj · ^T days · ^R dedup · ^O order · esc quit")

    def refilter():
        nonlocal base, filtered, sel
        base = base_hits()
        filtered = apply(base, query)
        sel = 0

    while True:
        h, w = stdscr.getmaxyx()
        if h < 6 or w < 24:
            stdscr.erase()
            _addstr(stdscr, 0, 0, "terminal too small", w)
            stdscr.refresh()
            if stdscr.getch() in (27, 3):
                return None
            continue
        preview_h = max(4, h // 4)
        legend_y = h - 1
        preview_top = legend_y - preview_h
        list_top, list_h = 2, max(1, (preview_top - 1) - 2)
        if filtered:
            sel = max(0, min(sel, len(filtered) - 1))
        top = max(0, sel - list_h + 1) if sel >= list_h else 0

        stdscr.erase()
        _addstr(stdscr, 0, 0, "> " + query, w, curses.A_BOLD)
        status = _status_tags(state, len(filtered), len(base))
        if flash:
            status += "   " + flash
        _addstr(stdscr, 1, 0, status, w, curses.A_DIM)
        for i in range(list_h):
            idx = top + i
            if idx >= len(filtered):
                break
            hh = filtered[idx]
            dt = when(hh["timestamp"])
            reps = f" ×{hh['_n']}" if hh["_n"] > 1 else ""
            proj = os.path.basename(hh.get("project", "") or "?")
            row = f"{pid(hh['display'])} {dt.strftime('%b %d')} {proj}{reps}  " \
                  f"{' '.join(hh['display'].split())}"
            _addstr(stdscr, list_top + i, 0, row, w,
                    curses.A_REVERSE if idx == sel else 0)
        _addstr(stdscr, preview_top - 1, 0, "─" * w, w, curses.A_DIM)
        if filtered:
            hh = filtered[sel]
            dt = when(hh["timestamp"])
            proj = os.path.basename(hh.get("project", "") or "?")
            meta = f"{pid(hh['display'])} · {dt.strftime('%Y-%m-%d %H:%M')} · {proj}"
            if hh["_n"] > 1:
                meta += f" · ×{hh['_n']}"
            _addstr(stdscr, preview_top, 0, meta, w, curses.A_BOLD)
            wrapped = []
            for para in hh["display"].split("\n"):
                wrapped.extend(textwrap.wrap(para, max(1, w - 1)) or [""])
            for j, ln in enumerate(wrapped[: preview_h - 1]):
                _addstr(stdscr, preview_top + 1 + j, 0, ln, w)
        else:
            _addstr(stdscr, preview_top, 0, "(no matches)", w)
        _addstr(stdscr, legend_y, 0, legend, w, curses.A_REVERSE)
        stdscr.refresh()

        ch = stdscr.getch()
        flash = ""
        if ch == curses.KEY_RESIZE:
            continue
        elif ch in (27, 3):
            return None
        elif ch in (curses.KEY_ENTER, 10, 13):
            if filtered:
                return ("print", filtered[sel]["display"])
        elif ch in (curses.KEY_UP, 16):
            sel = max(0, sel - 1)
        elif ch in (curses.KEY_DOWN, 14):
            sel = min(len(filtered) - 1, sel + 1) if filtered else 0
        elif ch == curses.KEY_NPAGE:
            sel = min(len(filtered) - 1, sel + list_h) if filtered else 0
        elif ch == curses.KEY_PPAGE:
            sel = max(0, sel - list_h)
        elif ch == 21:  # ^U clear query
            query = ""
            filtered = apply(base, query)
            sel = 0
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            query = query[:-1]
            filtered = apply(base, query)
            sel = 0
        elif ch == 25:  # ^Y copy prompt
            if filtered:
                tool = to_clipboard(filtered[sel]["display"])
                flash = f"copied prompt → {tool}" if tool else "clipboard unavailable (no tool / OSC52 blocked) — use ⏎ to print"
        elif ch == 2:  # ^B copy id
            if filtered:
                tool = to_clipboard(pid(filtered[sel]["display"]))
                flash = f"copied id → {tool}" if tool else "clipboard unavailable (no tool / OSC52 blocked) — use ⏎ to print"
        elif ch == 22:  # ^V view full text
            if filtered:
                hh = filtered[sel]
                dt = when(hh["timestamp"])
                proj = os.path.basename(hh.get("project", "") or "?")
                _viewer(stdscr, f"{pid(hh['display'])} · "
                        f"{dt.strftime('%Y-%m-%d %H:%M')} · {proj}", hh["display"])
        elif ch == 7:  # ^G project filter
            v = _ask(stdscr, 1, "project filter (empty=clear): ", w)
            if v is not None:
                state["project"] = v.strip() or None
                refilter()
        elif ch == 20:  # ^T last-N-days
            v = _ask(stdscr, 1, "last N days (empty=clear): ", w)
            if v is not None:
                state["days"] = int(v) if v.strip().isdigit() else None
                refilter()
        elif ch == 18:  # ^R toggle dedup
            state["no_dedup"] = not state["no_dedup"]
            refilter()
        elif ch == 15:  # ^O toggle order
            state["oldest"] = not state["oldest"]
            refilter()
        elif 32 <= ch <= 126:
            query += chr(ch)
            filtered = apply(base, query)
            sel = 0


def run_interactive(args):
    """Launch the picker. Returns True if it handled the request, False if curses
    is unavailable (caller then falls back to the non-interactive listing)."""
    try:
        import curses  # noqa: F401
    except Exception:
        return False
    rows = load()
    now = when(rows[0]["timestamp"]) if rows else datetime.datetime.now()
    state = {
        "query": " ".join(args.terms) if args.terms else "",
        "project": args.project,
        "days": args.days,
        "since": parse_date(args.since) if args.since else None,
        "since_str": args.since,
        "until": (parse_date(args.until) + datetime.timedelta(days=1)) if args.until else None,
        "until_str": args.until,
        "no_dedup": args.no_dedup,
        "oldest": args.oldest,
    }
    import curses
    try:
        result = curses.wrapper(_tui, rows, now, state)
    except Exception as e:
        print(f"(interactive mode failed: {e}; showing list)", file=sys.stderr)
        return False
    if result and result[0] == "print":
        print(result[1])
    return True


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("terms", nargs="*", help="search terms (AND, case-insensitive)")
    ap.add_argument("--regex", help="single regex pattern (overrides terms)")
    ap.add_argument("--project", help="only projects whose path contains this substring")
    ap.add_argument("--days", type=int, help="only entries within the last N days")
    ap.add_argument("--since", help="only entries on/after this date (YYYY-MM-DD)")
    ap.add_argument("--until", help="only entries on/before this date (YYYY-MM-DD)")
    ap.add_argument("--limit", type=int, default=30, help="max matches to show (default 30)")
    ap.add_argument("--full", action="store_true", help="show full prompt text (no truncation)")
    ap.add_argument("--width", type=int, default=TRUNC, metavar="N",
                    help=f"max characters shown per result before truncating (default {TRUNC}); --full overrides")
    ap.add_argument("--oldest", action="store_true", help="oldest matches first")
    ap.add_argument("--no-dedup", action="store_true", help="show every occurrence, don't collapse duplicates")
    ap.add_argument("--copy", "--show", dest="copy", metavar="N|ID",
                    help="print only that match's full text (by row number or stable id)")
    ap.add_argument("--clip", action="store_true",
                    help="with --copy, send the prompt to the system clipboard")
    ap.add_argument("--json", action="store_true", help="output matches as JSON")
    ap.add_argument("--projects", action="store_true", help="list projects with history")
    ap.add_argument("-i", "--interactive", action="store_true",
                    help="launch the interactive fuzzy picker (TTY only)")
    args = ap.parse_args()

    # Subcommand sugar: `ph copy N|ID [terms]` / `ph show N|ID [terms]` behave
    # like `--copy N|ID [terms]`. Only fires when the first word is copy/show
    # and the next looks like a row number or hex id, so ordinary searches such
    # as `ph copy paste` are left untouched.
    if (args.copy is None and len(args.terms) >= 2
            and args.terms[0].lower() in ("copy", "show")
            and re.fullmatch(r"[0-9a-fA-F]+", args.terms[1])):
        args.copy = args.terms[1]
        args.terms = args.terms[2:]

    # Interactive picker: only on a TTY, with no result flag, and either an
    # explicit -i or no query (see should_interactive). Falls through to the
    # normal listing if curses is unavailable.
    if should_interactive(args, sys.stdout.isatty()):
        if run_interactive(args):
            return
        print("(interactive mode unavailable: curses not importable; showing list)",
              file=sys.stderr)

    rows = load()
    total = len(rows)
    now = when(rows[0]["timestamp"]) if rows else datetime.datetime.now()

    if args.projects:
        projects_overview(rows)
        return

    since = parse_date(args.since) if args.since else None
    until = (parse_date(args.until) + datetime.timedelta(days=1)) if args.until else None
    terms = args.terms if (args.terms and not args.regex) else []
    hits = collect_hits(rows, terms=(args.terms or None), regex=args.regex,
                        project=args.project, days=args.days, since=since, until=until,
                        no_dedup=args.no_dedup, oldest=args.oldest, now=now)

    # --copy / --show: dump one entry raw and stop. Accepts a row number or a
    # stable id (content hash). Optionally pipe it to the system clipboard.
    if args.copy is not None:
        ref = args.copy.strip()
        sel = None
        if ref.isdigit() and 1 <= int(ref) <= len(hits):
            sel = hits[int(ref) - 1]
        else:
            cands = [h for h in hits if pid(h["display"]).startswith(ref.lower())]
            if len(cands) == 1:
                sel = cands[0]
            elif len(cands) > 1:
                print(f"(id {ref!r} is ambiguous — matches {len(cands)} prompts; use more characters)")
                return
        if sel is None:
            print(f"(no match {ref!r}; there are {len(hits)} hits — use 1..{len(hits)} or a listed id)")
            return
        text = sel["display"]
        if args.clip:
            tool = to_clipboard(text)
            note = (f"copied to clipboard via {tool}" if tool
                    else "clipboard unavailable (no tool / tmux / OSC52); printed below instead")
            print(note, file=sys.stderr)
        print(text)
        return
    if args.clip:
        print("--clip only applies with --copy/--show N|ID", file=sys.stderr)

    shown = hits[: args.limit]
    q = args.regex or (" ".join(terms) if terms else "(recent, all projects)")

    if args.json:
        print(json.dumps([
            {"rank": i, "id": pid(r["display"]),
             "timestamp": when(r["timestamp"]).isoformat(timespec="seconds"),
             "project": r.get("project", ""), "count": r["_n"], "display": r["display"]}
            for i, r in enumerate(shown, 1)
        ], indent=2, ensure_ascii=False))
        return

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
        if not args.full and len(text) > args.width:
            text = (text[: args.width - 3] + "...") if args.width > 3 else text[: args.width]
        if terms:
            text = highlight(text, terms)
        print(f"[{i}] {pid(r['display'])} · {stamp} · {rel(dt, now):>9}  ({proj}){reps}\n    {text}\n")
    if len(hits) > len(shown):
        print(f"... {len(hits) - len(shown)} more — add a term to narrow or raise --limit.")
    print("Reply with a number to rerun that prompt, or `--copy N|ID` "
          "(add `--clip` to copy to clipboard) / `--full` for complete text.")


if __name__ == "__main__":
    main()
