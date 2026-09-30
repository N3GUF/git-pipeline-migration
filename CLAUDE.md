# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Two CLIs sharing one repo/venv:

- `git-pipeline-migration` migrates Control-M folder/job definition exports (JSON): it replaces job `Command` values per a CSV mapping, then strips legacy job-name prefixes (and matching text in descriptions), writing the result to a new JSON file. Every job touched by either step gets the CLI's `--update-comment` appended to its Description exactly once, even if touched by both.
- `xlsx-path-updater` annotates a separate job-inventory workbook (`.xlsx`, not part of the JSON migration) with two columns, `Original Path` and `Updated Path`, driven by the same commands CSV.

## Commands

```bash
uv sync                      # install/update the venv from pyproject.toml + uv.lock

uv run git-pipeline-migration \
  --jobs-json data/cfnauth_jobs.json \
  --commands-csv commands.csv \
  --output-json data/cfnauth_jobs_updated.json \
  --update-comment "Updated per PRJTASK0190790 CFN Migration" \
  [--log-level DEBUG]

uv run xlsx-path-updater \
  --xlsx-path "data/CFN Auth Jobs.xlsx" \
  --commands-csv "data/cfn_auth_controlm_jobs(Sheet1).csv" \
  [--log-level DEBUG]

uv run ruff check .          # lint
uv run ruff format --check . # verify formatting
```

The CSV must have columns `Existing Command Line` and `New Command Line Path` (other columns, e.g. Host/Server/Job Name, are ignored — matching is by command text only). A row is a no-op (no update applied) when the new command is blank or identical to the existing one. Read with `utf-8-sig` to tolerate a BOM from Excel exports (see `data/cfn_auth_controlm_jobs(Sheet1).csv` for a real example).

`xlsx-path-updater` reads that same CSV via `git_pipeline_migration.commands.load_command_replacements` (no duplicated CSV-parsing logic) and matches rows in the workbook by exact text against its `Command Line` column — no job-name lookup, same matching convention as `git-pipeline-migration` itself. It edits the workbook **in place**: `Original Path` is always set to that row's existing `Command Line` value, and `Updated Path` is set to the CSV's replacement or left blank if that command has no update. Rerunning it is idempotent — it reuses existing `Original Path`/`Updated Path` columns by header name rather than appending duplicates.

Each CLI writes its own `logging` output to `<prog-name>.log` in the current working directory (appended across runs, not overwritten); only summary counts are printed to the console.

No test suite is configured yet.

## Architecture

Package: `src/git_pipeline_migration/` (src layout, entry point `git-pipeline-migration` defined in `pyproject.toml` under `[project.scripts]`, pointing at `git_pipeline_migration:main` which re-exports `cli.main`).

Processing order matters and is fixed in `cli.main`: **commands are replaced before prefixes are stripped.**

- `job_walker.py` — `iter_jobs(data)` recursively walks the folder JSON and yields `(container, job_key)` for every entry whose `Type` starts with `"Job:"`. `container` is the actual parent dict, so callers mutate/rename jobs in place via `container[job_key]`. This is the only traversal logic; both later stages consume its output rather than re-walking the tree.
- `descriptions.py` — `append_comment_if_missing(job, comment)` is the single place that appends `--update-comment` to a job's Description (space-separated, or as the whole description if none existed), skipping the append if that exact comment text is already present. Shared by `commands.py` and `prefixes.py` so a job touched by both stages doesn't end up with the comment twice. Deliberately joins with a plain space, not `\n` — Control-M's own exports encode line breaks within Description as a literal two-character `\n` (backslash + n), not an actual newline byte, and an actual newline byte doesn't match that convention when re-imported.
- `commands.py` — `load_command_replacements` parses the CSV's `Existing Command Line`/`New Command Line Path` columns into a dict (skipping no-op rows, warning on conflicting duplicate keys). `apply_command_replacements` matches purely on the job's `Command` *text* — there is no job-name/folder lookup — so one CSV row can update many jobs that happen to share a command. Every job it updates calls `append_comment_if_missing`.
- `prefixes.py` — `PREFIXES_TO_STRIP` is a hardcoded list of legacy job-name prefixes (e.g. `AUTAPP1_`, `mir01_`, `mir02_`, `sheila_`); there is intentionally no CLI flag to override it. `apply_prefix_stripping` groups jobs by their containing folder and, per folder, precomputes what every job's name would become after stripping — if two or more jobs in the same folder would collide on the same resulting name, **none of them are renamed** (and their description is left alone, comment included) — a warning is logged for each and the run continues. Otherwise it renames the job's dict key (via `_rename_key`, which rebuilds the parent dict to preserve key order), removes the literal prefix substring from `Description` if present, and calls `append_comment_if_missing`.
- `cli.py` — wires the three stages together (commands replaced, *then* prefixes stripped — order doesn't affect the comment logic since it's idempotent either way), configures `logging.basicConfig` to append to `LOG_FILE` (`f"{PROG_NAME}.log"`) at `--log-level`, and reports three counts: jobs read, jobs updated (command replaced), jobs renamed (prefix stripped). These are independent counters — a job can be counted in either, both, or neither.

The input JSON shape is a Control-M export: top-level keys are folders (`Type: SimpleFolder`, etc.) containing job entries (`Type: Job:Command`, etc.) as nested dicts; job entries themselves contain further nested dicts (`Rerun`, `When`, `IfBase:...`) that are *not* jobs or folders — `iter_jobs` relies on the `Type` prefix check to avoid descending into those.

Sample data lives in `data/cfnauth_jobs.json` (real Control-M export, not synthetic).

Package: `src/xlsx_path_updater/` (entry point `xlsx-path-updater`, pointing at `xlsx_path_updater:main` which re-exports `cli.main`). Single-module CLI (`cli.py`) that depends on `openpyxl` and imports `load_command_replacements` from `git_pipeline_migration.commands` rather than re-parsing the CSV. It locates columns by header text in row 1 (`_header_index_map`), adding `Original Path`/`Updated Path` if not already present (`_column_index`), then walks data rows, skipping fully-blank trailing rows, and writes both columns before saving the workbook back to `--xlsx-path`.
