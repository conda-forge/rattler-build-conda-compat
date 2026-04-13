from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any


def is_staging_output(output: Mapping[str, Any]) -> bool:
    """Return True if *output* is a staging output (no artifact)."""
    return "staging" in output and "package" not in output


def iter_package_outputs(
    outputs: list[Mapping[str, Any]],
) -> Iterator[Mapping[str, Any]]:
    """Yield only outputs that produce a package."""
    return (o for o in outputs if not is_staging_output(o))


def get_output_name(output: Mapping[str, Any]) -> str | None:
    """Return the declared name of a `package:` or `staging:` output, or None."""
    for key in ("package", "staging"):
        section = output.get(key)
        if isinstance(section, Mapping):
            name = section.get("name")
            if isinstance(name, str):
                return name
    return None
