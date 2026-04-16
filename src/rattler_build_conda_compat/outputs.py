from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping, MutableMapping
from typing import Any

from rattler_build_conda_compat.yaml import _dump_yaml_to_string, _yaml_object


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


def _inherit_target(output: Mapping[str, Any]) -> str | None:
    """Return the staging output name an output inherits from, or None.

    `inherit:` may be a bare string (`inherit: libfoo-build`) or a mapping
    (`inherit: {from: libfoo-build, run_exports: false}`).
    """
    inherit = output.get("inherit")
    if isinstance(inherit, str):
        return inherit
    if isinstance(inherit, Mapping):
        target = inherit.get("from")
        if isinstance(target, str):
            return target
    return None


def _merge_requirement_section(
    target: MutableMapping[str, Any],
    source: Mapping[str, Any],
    key: str,
) -> None:
    source_values = source.get(key)
    if not source_values:
        return
    existing = target.get(key) or []
    if not isinstance(existing, list):
        existing = [existing]
    if not isinstance(source_values, list):
        source_values = [source_values]
    merged: list[Any] = list(source_values)
    for item in existing:
        if item not in merged:
            merged.append(item)
    target[key] = merged


def _index_staging_outputs(
    outputs: list[Any],
) -> dict[str, Mapping[str, Any]]:
    """Build a name-keyed index of staging outputs."""
    staging_by_name: dict[str, Mapping[str, Any]] = {}
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        if is_staging_output(output):
            name = get_output_name(output)
            if name is not None:
                staging_by_name[name] = output
    return staging_by_name


def _apply_staging_inheritance(
    output: MutableMapping[str, Any],
    staging: Mapping[str, Any],
) -> None:
    """Merge requirements and source from *staging* into *output*."""
    staging_reqs = staging.get("requirements") or {}
    if isinstance(staging_reqs, Mapping):
        output_reqs = output.get("requirements")
        if not isinstance(output_reqs, MutableMapping):
            output_reqs = {}
            output["requirements"] = output_reqs
        for section in ("build", "host"):
            _merge_requirement_section(output_reqs, staging_reqs, section)

    if "source" not in output and "source" in staging:
        # deep-copy so multiple inheriting outputs do not share a
        # ruamel node, which would serialize back as yaml anchors.
        output["source"] = copy.deepcopy(staging["source"])


def flatten_staging_inheritance(recipe_text: str) -> str:
    """Return *recipe_text* with staging inheritance resolved.

    For each output that declares ``inherit:`` pointing at a staging output,
    the staging output's ``requirements.build`` and ``requirements.host`` are
    prepended to the inheriting output's own build and host lists, and the
    staging output's ``source:`` is copied to the inheriting output if it has
    none of its own. Staging outputs and the ``inherit:`` keys are removed,
    yielding a recipe that no longer uses the experimental staging feature
    while preserving the full dependency and source surface that downstream
    consumers (dep graph, variant computation, version migrators) need to see.

    The input string is returned unchanged when the recipe has no staging
    outputs, so callers can use this helper unconditionally.
    """
    if "staging" not in recipe_text:
        return recipe_text

    recipe = _yaml_object().load(recipe_text)
    if not isinstance(recipe, MutableMapping):
        return recipe_text

    outputs = recipe.get("outputs")
    if not isinstance(outputs, list):
        return recipe_text

    staging_by_name = _index_staging_outputs(outputs)
    if not staging_by_name:
        return recipe_text

    surviving: list[Any] = []
    for output in outputs:
        if not isinstance(output, MutableMapping):
            surviving.append(output)
            continue
        if is_staging_output(output):
            continue

        target_name = _inherit_target(output)
        if target_name is not None:
            staging = staging_by_name.get(target_name)
            if staging is not None:
                _apply_staging_inheritance(output, staging)

        output.pop("inherit", None)
        surviving.append(output)

    recipe["outputs"] = surviving
    return _dump_yaml_to_string(recipe)
