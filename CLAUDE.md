# CLAUDE.md — claude-ph

Guidance for Claude Code when this repository is open. Its purpose is to let a
user install (or update) the `/ph` prompt-history search tool just by asking.

## What this repo is

A Claude Code tool that searches the user's **full** prompt history
(`~/.claude/history.jsonl`) across all projects and all time — bypassing the
native `Ctrl+R` picker's documented limit of the 100 most recent unique prompts.

- `ph.py` — the searcher (Python 3, standard library only, read-only).
- `ph.md` — the `/ph` custom slash command that runs `ph.py` and injects results.
- `ph` — an optional one-line shell shim (`~/.local/bin/ph`) that runs the same
  searcher with no model turn, for zero-token searches from a terminal or `!ph`.

## Install / update on request

When the user asks to **install**, **set up**, or **update** this tool, do this
without further prompting:

1. Create the target directories (idempotent):
   ```sh
   mkdir -p ~/.claude/scripts ~/.claude/commands ~/.local/bin
   ```
2. Copy the artifacts from this repo to their install locations:
   ```sh
   cp ph.py ~/.claude/scripts/ph.py
   cp ph.md ~/.claude/commands/ph.md
   cp ph    ~/.local/bin/ph && chmod +x ~/.local/bin/ph   # zero-token shell command
   ```
   (Or just run `./install.sh`, which does all of the above and warns if
   `~/.local/bin` is not on `PATH`.)
3. Verify the files copied (non-empty, exit status 0).
4. Tell the user to **restart Claude Code** so the new `/ph` command is loaded,
   then they can run e.g. `/ph deploy` — or `ph deploy` from any shell for a
   zero-token search (mention they may need `~/.local/bin` on their `PATH`).

If `~/.claude/scripts/ph.py` or `~/.claude/commands/ph.md` already exist, treat
the action as an update: overwrite them with the repo versions and mention that
you replaced an existing install.

## Constraints

- **Read-only against the user's history.** `ph.py` only reads
  `~/.claude/history.jsonl`; it never writes or deletes anything under
  `~/.claude`. Do not add code that mutates the user's Claude config or history.
- **No dependencies.** Keep `ph.py` to the Python standard library so install is
  a plain file copy with nothing to `pip install`.
- **Generic paths only.** Reference `~/.claude/...` (tilde-relative), never a
  specific user's absolute home path, in any committed file.

## Uninstall

```sh
rm -f ~/.claude/scripts/ph.py ~/.claude/commands/ph.md ~/.local/bin/ph
```

Then restart Claude Code. Nothing else is touched.
