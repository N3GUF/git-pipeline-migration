"""Shared helper for appending an update comment to a job's Description."""

from __future__ import annotations


def append_comment_if_missing(job: dict, comment: str) -> None:
    """Append `comment` to job's Description, unless it's already present.

    Used by both the command-replacement and prefix-stripping stages so a job
    touched by both only ever gets the comment appended once.
    """
    description = job.get("Description")
    if isinstance(description, str) and description:
        if comment not in description:
            job["Description"] = f"{description} {comment}"
    else:
        job["Description"] = comment
