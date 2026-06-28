---
description: Search your FULL Claude Code prompt history (all projects, all time) — bypasses the native 100-entry Ctrl+R cap
argument-hint: [terms] | --full | --copy N|ID | --show N|ID | --clip | --json | --project NAME | --since DATE | --until DATE | --days N | --no-dedup | --oldest | --regex P | --projects
allowed-tools: Bash(python3:*)
---

!`python3 ~/.claude/scripts/ph.py $ARGUMENTS`

Above are the user's matching past prompts (numbered, newest first, duplicates collapsed with ×N repeat counts).

Now help them act on it:
- If they later reply with just a **number** (e.g. "3"), treat match #3 as the prompt they want to reuse: restate it and **execute it as if they had typed it**, adapting any stale paths/details to the current project.
- If they say "edit N: ..." adapt that prompt per their note, then run it.
- If nothing matched, suggest broadening (fewer terms, drop `--project`/`--days`, or `/ph --projects`).
- Keep your reply tight — they came here to recall a prompt, not read commentary.
