"""Load command replacements from CSV and apply them to job definitions by Command text."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from .descriptions import append_comment_if_missing

logger = logging.getLogger(__name__)

EXISTING_COMMAND_COLUMN = "Existing Command Line"
REPLACEMENT_COMMAND_COLUMN = "New Command Line Path"
REQUIRED_COLUMNS = {EXISTING_COMMAND_COLUMN, REPLACEMENT_COMMAND_COLUMN}


def load_command_replacements(csv_path: Path) -> dict[str, str]:
    """Read existing/replacement command pairs from a CSV file.

    Rows are skipped (with no update needed) when the replacement command is
    blank, or identical to the existing command.
    """
    replacements: dict[str, str] = {}
    skipped = 0

    # utf-8-sig transparently strips a leading BOM (e.g. from Excel-exported CSVs).
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = {name.strip() for name in (reader.fieldnames or [])}
        if not REQUIRED_COLUMNS.issubset(fieldnames):
            raise ValueError(
                f"{csv_path} must have columns {sorted(REQUIRED_COLUMNS)}; "
                f"found {reader.fieldnames}"
            )

        for row in reader:
            existing = (row.get(EXISTING_COMMAND_COLUMN) or "").strip()
            replacement = (row.get(REPLACEMENT_COMMAND_COLUMN) or "").strip()

            if not existing:
                continue
            if not replacement:
                logger.debug("No update needed for %r: replacement command is empty", existing)
                skipped += 1
                continue
            if replacement == existing:
                logger.debug(
                    "No update needed for %r: replacement matches existing command", existing
                )
                skipped += 1
                continue

            if existing in replacements and replacements[existing] != replacement:
                logger.warning(
                    "Duplicate existing command %r in CSV with conflicting replacements; "
                    "using the last one seen (%r)",
                    existing,
                    replacement,
                )
            replacements[existing] = replacement

    logger.info(
        "Loaded %d command replacement(s) from %s (%d row(s) needed no update)",
        len(replacements),
        csv_path,
        skipped,
    )
    return replacements


def apply_command_replacements(
    jobs: list[tuple[dict, str]], replacements: dict[str, str], update_comment: str
) -> int:
    """Replace each job's Command field per `replacements`. Returns count of jobs updated.

    Every updated job also gets `update_comment` appended to its Description.
    """
    updated = 0
    for container, key in jobs:
        job = container[key]
        command = job.get("Command")
        new_command = replacements.get(command)
        if new_command is None:
            continue
        logger.info("Job %r: Command updated %r -> %r", key, command, new_command)
        job["Command"] = new_command
        append_comment_if_missing(job, update_comment)

        updated += 1
    return updated
