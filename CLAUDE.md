# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Two CLIs:

- `git-pipeline-migration` migrates Control-M folder/job definition exports (JSON): it replaces job `Command` values per a CSV mapping, writing the result to a new JSON file. Every job updated gets the CLI's `--update-comment` appended to its Description exactly once. The legacy job-name prefix stripping stage (`prefixes.py`) is currently **disabled** in `cli.main` (call and reporting commented out); the module is kept so it can be re-enabled.
- `update-job-inventory` annotates a separate job-inventory workbook (`.xlsx`, not part of the JSON migration) with `Original Path` and `Updated Path` columns.

## Commands

```bash
uv sync                      # install/update the venv from pyproject.toml + uv.lock

uv run git-pipeline-migration \
  --jobs-json data/cfnauth_jobs.json \
  --commands-csv commands.csv \
  --output-json data/cfnauth_jobs_updated.json \
  --update-comment "Updated per PRJTASK0190790 CFN Migration" \
  [--log-level DEBUG]

uv run update-job-inventory \
  --input "data/CFN Auth Jobs.xlsx" \
  --output data/CFN_Auth_Jobs_updated.xlsx \
  [--updated-path /opt/new/dir] \
  [--log-level DEBUG]

uv run ruff check .          # lint
uv run ruff format --check . # verify formatting
```

The CSV must have columns `Existing Command Line` and `New Command Line Path` (other columns, e.g. Host/Server/Job Name, are ignored — matching is by command text only). A row is a no-op (no update applied) when the new command is blank or identical to the existing one. Read with `utf-8-sig` to tolerate a BOM from Excel exports (see `data/cfn_auth_controlm_jobs(Sheet1).csv` for a real example).

`update-job-inventory` fills `Original Path` with the **directory only** (never the file) of the first absolute path (POSIX, `~/`, or Windows drive) found in: `Command Line` when `Task Type` is `Command`; `File Path/Member Library`, falling back to `Embedded Script`, when `Task Type` is `Job`. Rows with no path get a blank value and a logged warning. `--updated-path`, if given, is written to `Updated Path` on every data row; otherwise that column is left untouched. Existing `Original Path`/`Updated Path` headers are reused (found by header text), so reruns don't add duplicate columns; otherwise they are appended on the right. It reads and writes the workbook's active sheet.

Each CLI writes its `logging` output to `<prog-name>.log` in the current working directory (appended across runs, not overwritten); only summary counts are printed to the console.

No test suite is configured yet.

## Architecture

Package: `src/git_pipeline_migration/` (src layout, entry point `git-pipeline-migration` defined in `pyproject.toml` under `[project.scripts]`, pointing at `git_pipeline_migration:main` which re-exports `cli.main`).

Only the command-replacement stage currently runs in `cli.main`. If prefix stripping is re-enabled, **commands are replaced before prefixes are stripped.**

- `job_walker.py` — `iter_jobs(data)` recursively walks the folder JSON and yields `(container, job_key)` for every entry whose `Type` starts with `"Job:"`. `container` is the actual parent dict, so callers mutate/rename jobs in place via `container[job_key]`. This is the only traversal logic; both later stages consume its output rather than re-walking the tree.
- `descriptions.py` — `append_comment_if_missing(job, comment)` is the single place that appends `--update-comment` to a job's Description (space-separated, or as the whole description if none existed), skipping the append if that exact comment text is already present. Shared by `commands.py` and `prefixes.py` so a job touched by both stages doesn't end up with the comment twice. Deliberately joins with a plain space, not `\n` — Control-M's own exports encode line breaks within Description as a literal two-character `\n` (backslash + n), not an actual newline byte, and an actual newline byte doesn't match that convention when re-imported.
- `commands.py` — `load_command_replacements` parses the CSV's `Existing Command Line`/`New Command Line Path` columns into a dict (skipping no-op rows, warning on conflicting duplicate keys). `apply_command_replacements` matches purely on the job's `Command` *text* — there is no job-name/folder lookup — so one CSV row can update many jobs that happen to share a command. Every job it updates calls `append_comment_if_missing`.
- `prefixes.py` — **Currently disabled** (not called from `cli.main`). `PREFIXES_TO_STRIP` is a hardcoded list of legacy job-name prefixes (e.g. `AUTAPP1_`, `mir01_`, `mir02_`, `sheila_`); there is intentionally no CLI flag to override it. `apply_prefix_stripping` groups jobs by their containing folder and, per folder, precomputes what every job's name would become after stripping — if two or more jobs in the same folder would collide on the same resulting name, **none of them are renamed** (and their description is left alone, comment included) — a warning is logged for each and the run continues. Otherwise it renames the job's dict key (via `_rename_key`, which rebuilds the parent dict to preserve key order), removes the literal prefix substring from `Description` if present, and calls `append_comment_if_missing`.
- `cli.py` — runs command replacement only (the prefix-stripping call, its log line and its console line are commented out), configures `logging.basicConfig` to append to `LOG_FILE` (`f"{PROG_NAME}.log"`) at `--log-level`, and reports two counts: jobs read and jobs updated (command replaced). If prefix stripping is re-enabled, it runs *after* command replacement (order doesn't affect the comment logic since it's idempotent either way) and a third "jobs renamed" count returns; the counters are independent, so a job can be counted in either, both, or neither.

The input JSON shape is a Control-M export: top-level keys are folders (`Type: SimpleFolder`, etc.) containing job entries (`Type: Job:Command`, etc.) as nested dicts; job entries themselves contain further nested dicts (`Rerun`, `When`, `IfBase:...`) that are *not* jobs or folders — `iter_jobs` relies on the `Type` prefix check to avoid descending into those.

Package: `src/update_job_inventory/` (entry point `update-job-inventory`, pointing at `update_job_inventory:main` which re-exports `cli.main`). Single-module CLI (`cli.py`) depending on `openpyxl`; it is independent of `git_pipeline_migration`. `first_directory` does the path extraction (regex-based), `update_workbook` locates columns by header text in row 1 and fills the two columns in place.

Sample data lives in `data/cfnauth_jobs.json` (real Control-M export, not synthetic).
