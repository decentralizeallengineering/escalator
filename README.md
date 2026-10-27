# escalator

A small pipeline that spends strong-model effort only where a cheap model failed.

1. A local model drafts a patch for one task row, as SEARCH/REPLACE edit blocks applied in a throwaway git worktree.
2. Your gate command (tests) runs, and a diff rule check refuses protected paths and oversized diffs.
3. A cheap reviewer reads the diff and answers `OK` or `REJECT: reason`.
4. Failures are fed back to the draft model for a few tries. If it is still red, a stronger model fixes it once.
5. Only a green, reviewed result is committed, on a branch `esc/<id>`. Nothing is pushed or merged: you land it.

Task text is passed to every model as quoted data, not as instructions.

## Install

Python 3.9+ and git. Put `bin/` on your `PATH` (the scripts find `lib/` next to them).

## Configure

Copy `escalator.example.json` to `escalator.json` (or `~/.config/escalator/config.json`, or set `ESCALATOR_CONFIG`).
Each model is a "stage": either `{"url": ".../v1", "model": "name", "api_key_env": "VAR"}` for any OpenAI-compatible server, or
`{"cmd": "shell command"}` that gets the prompt on stdin and prints the reply (the `fix` command runs inside the worktree and may edit files
directly, like an agent CLI; `$ESCALATOR_WORKTREE` is set). Other keys: `repo`, `base_branch`, `gate_cmd`, `protected` globs, `max_diff_lines`, `tries`, `rules`.

The task file (`tasks`) is plain markdown or JSON, see `tasks.example.md` and `tasks.example.json`: an `id` column or key,
the task `text`, optional `files` to edit (otherwise the file hitting most keywords is used), optional `status` (`closed` rows are skipped).

## Example

```
escalate T1                       # one task: draft, gate, review, fix on red; prints a JSON result line
escalate-batch 3 --dry-run        # list the open tasks
escalate-batch 3 --limit 10       # run them 3 at a time (draft and review only; add --fix to allow the strong model)
```

`escalate-batch` records `results.tsv` in the log directory, skips finished tasks, and supports `--shard k/n` for several lanes.

## Tests

`python3 -m unittest discover -s tests` runs the whole pipeline in a temporary repo with shell-command stub models.

## License

Apache-2.0, see `LICENSE` and `NOTICE`.
