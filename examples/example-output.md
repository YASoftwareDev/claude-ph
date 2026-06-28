# Example `/ph` session

> The data below is **synthetic** — illustrative project names and prompts, not
> anyone's real history. It shows the shape of the output you get in a real run.

## Searching across all projects

You type a search inside a Claude Code session:

```
/ph deploy staging
```

`/ph` scans your full `~/.claude/history.jsonl` and injects the matches back into
the conversation:

```
prompt-history: 6 unique match for 'deploy staging'  (scanned 4821 prompts, showing 6)

[1] 3e9a1c7 · Jun 12 09:14 ·    9d ago  (web-dashboard)  ×4
    redeploy the **staging** environment after the pipeline fix and confirm the
    health checks pass before promoting to prod

[2] b042f5a · May 28 16:02 ·     3w ago  (web-dashboard)
    why does the **staging** **deploy** hang on the migration step? check the helm
    values and the readiness probe timeout

[3] 7c5d80e · May 03 11:40 ·     1mo ago  (billing-api)
    write a GitHub Actions job that runs the **deploy**-to-**staging** smoke tests
    on every PR labelled "release"

... 3 more — add a term to narrow or raise --limit.
Reply with a number to rerun that prompt, or `--copy N|ID` (add `--clip` to copy to clipboard) / `--full` for complete text.
```

- Results are **numbered**, newest first.
- `3e9a1c7` is the prompt's **stable id** — a hash of its text. Use it with
  `--copy <id>`; unlike the row number, it never shifts as history grows.
- `(web-dashboard)` is the project the prompt came from.
- `×4` means that exact prompt was used 4 times — duplicates are **collapsed**.
- Your search terms (`staging`, `deploy`) are **highlighted**.

## Rerun-by-number

You reply with just:

```
1
```

Claude treats match #1 as the prompt you want to reuse — restating it and running
it, adapting any stale paths to your current project. `edit 1: but target prod`
tweaks it first.

## One prompt, raw — `--copy`

```
/ph --copy 2 deploy staging          # by row number
/ph --copy b042f5a deploy staging    # by stable id (same prompt, even if it moved)
```

Prints only that match's full text, with nothing else around it, ready to copy:

```
why does the staging deploy hang on the migration step? check the helm
values and the readiness probe timeout
```

From a shell you can send it straight to the clipboard — no mouse-selecting:

```sh
ph --copy b042f5a deploy staging --clip
```

## Project overview — `--projects`

```
/ph --projects
```

```
prompt-history: 18 projects, 4821 total prompts

    932  2026-02-11 -> 2026-06-20  web-dashboard
    640  2026-03-02 -> 2026-06-18  billing-api
    410  2026-01-22 -> 2026-05-30  data-pipeline
    ...

Tip: /ph --project NAME <terms>  to search inside one project.
```
