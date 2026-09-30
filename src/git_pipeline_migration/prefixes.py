"""Strip legacy naming prefixes from job names and descriptions."""

from __future__ import annotations

import logging
from collections import Counter

from .descriptions import append_comment_if_missing

logger = logging.getLogger(__name__)

# Hard-coded legacy job-name prefixes to remove during migration.
PREFIXES_TO_STRIP: list[str] = [
    "AUTAPP1_",
    "autapp1_",
    "autmirapp1_",
    "cfnautapp1_",
    "mir01_",
    "mir02_",
    "sheila_",
    "nanu2_",
]


def _strip_prefix(name: str) -> tuple[str, str | None]:
    """Return (name-without-prefix, matched-prefix) for the first matching prefix, if any."""
    for prefix in PREFIXES_TO_STRIP:
        if name.startswith(prefix):
            return name[len(prefix) :], prefix
    return name, None


def _rename_key(container: dict, old_key: str, new_key: str) -> None:
    if old_key == new_key:
        return
    items = [(new_key if k == old_key else k, v) for k, v in container.items()]
    container.clear()
    container.update(items)


def apply_prefix_stripping(jobs: list[tuple[dict, str]], update_comment: str) -> int:
    """Strip legacy prefixes from job names and their descriptions, in place.

    Renames the job's dict key, removes the literal prefix text from the
    job's Description field if present, and appends `update_comment` to the
    Description (skipped if that exact comment is already there, e.g. because
    the same job's Command was also replaced). Returns the count of jobs
    renamed.

    If stripping a prefix would make two or more jobs in the same folder end
    up with the same name, none of the colliding jobs are renamed (or have
    their description touched) -- a warning is logged for each and the run
    continues, leaving those jobs' prefixes in place.
    """
    # Group (container, key) pairs by the folder they live in, since name
    # collisions are only possible between jobs in the same folder.
    groups: dict[int, tuple[dict, list[str]]] = {}
    for container, key in jobs:
        group = groups.setdefault(id(container), (container, []))
        group[1].append(key)

    renamed = 0
    for container, keys in groups.values():
        final_names = {key: _strip_prefix(key)[0] for key in keys}
        name_counts = Counter(final_names.values())

        for key in keys:
            new_key, prefix = _strip_prefix(key)
            if prefix is None:
                continue

            if name_counts[new_key] > 1:
                logger.warning(
                    "Skipping rename of job %r -> %r: collides with another job "
                    "in the same folder after stripping prefix %r; left unrenamed",
                    key,
                    new_key,
                    prefix,
                )
                continue

            job = container[key]
            description = job.get("Description")
            if isinstance(description, str) and prefix in description:
                job["Description"] = description.replace(prefix, "")
            append_comment_if_missing(job, update_comment)

            _rename_key(container, key, new_key)
            renamed += 1
            logger.info("Renamed job %r -> %r (stripped prefix %r)", key, new_key, prefix)

    return renamed
