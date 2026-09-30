"""Recursive traversal helpers for Control-M folder/job JSON exports."""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any

_JOB_TYPE_PREFIX = "Job:"


def is_job(entry: Any) -> bool:
    """Return True if entry is a Control-M job definition (e.g. Type == 'Job:Command')."""
    return isinstance(entry, dict) and str(entry.get("Type", "")).startswith(_JOB_TYPE_PREFIX)


def iter_jobs(data: MutableMapping[str, Any]) -> Iterator[tuple[dict, str]]:
    """Recursively yield (container, job_key) for every job definition under data.

    `container` is the actual folder dict holding the job, so callers can read,
    mutate, or rename the job entry in place via container[job_key].
    """
    for key, value in list(data.items()):
        if is_job(value):
            yield data, key
        elif isinstance(value, dict):
            yield from iter_jobs(value)
