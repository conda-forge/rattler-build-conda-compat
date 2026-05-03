from __future__ import annotations

import contextlib
from typing import Any, Mapping, TypedDict

import jinja2
from jinja2 import UndefinedError
from jinja2.sandbox import SandboxedEnvironment

from rattler_build_conda_compat.jinja.filters import _bool, _split, _version_to_build_string
from rattler_build_conda_compat.jinja.objects import (
    _stub_compatible_pin,
    _stub_match,
    _stub_subpackage_pin,
    _StubEnv,
)
from rattler_build_conda_compat.jinja.utils import _MissingUndefined
from rattler_build_conda_compat.loader import load_yaml
from rattler_build_conda_compat.yaml import _dump_yaml_to_string


class RecipeWithContext(TypedDict, total=False):
    context: dict[str, str]


def jinja_env(variant_config: Mapping[str, str]) -> SandboxedEnvironment:
    """
    Create a `rattler-build` specific Jinja2 environment with modified syntax.

    `variant_config` must provide the variant variables that the recipe's
    context section may reference (e.g. `target_platform`, `build_platform`,
    plus any compiler/runtime keys used in expressions like
    `${{ (foo | split('.'))[1] | int }}`). Without those, rendering recipe
    contexts that perform operations on undefined values raises
    `UndefinedError`, so callers must pass an explicit variant.
    """

    env = SandboxedEnvironment(
        variable_start_string="${{",
        variable_end_string="}}",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=jinja2.select_autoescape(default_for_string=False),
        undefined=_MissingUndefined,
    )

    env_obj = _StubEnv()

    extra_vars = {}
    target_platform = variant_config.get("target_platform", "linux-64")
    if target_platform != "noarch":
        # set `linux` / `win`
        platform, arch = target_platform.split("-")
        extra_vars[platform] = True
        if arch == "64":
            extra_vars["x86_64"] = True
        elif arch == "32":
            extra_vars["x86"] = True
        else:
            extra_vars[arch] = True

    if target_platform.startswith("win"):
        extra_vars["unix"] = False
    else:
        extra_vars["unix"] = True

    env.globals.update(
        {
            "compiler": lambda x: x + "_compiler_stub",
            "stdlib": lambda x: x + "_stdlib_stub",
            "pin_subpackage": _stub_subpackage_pin,
            "pin_compatible": _stub_compatible_pin,
            "cdt": lambda *args, **kwargs: "cdt_stub",  # noqa: ARG005
            "env": env_obj,
            "match": _stub_match,
            "is_unix": lambda x: not x.startswith("win"),
            "is_win": lambda x: x.startswith("win"),
            "is_linux": lambda x: x.startswith("linux"),
            **extra_vars,
            **variant_config,
        }
    )

    # inject rattler-build recipe filters in jinja environment
    env.filters.update(
        {
            "version_to_buildstring": _version_to_build_string,
            "split": _split,
            "bool": _bool,
        }
    )
    return env


def load_recipe_context(context: dict[str, str], jinja_env: jinja2.Environment) -> dict[str, str]:
    """
    Load all string values from the context dictionary as Jinja2 templates.

    Entries that fail with `UndefinedError` (e.g. variant-dependent
    expressions like `${{ (foo | split('.'))[1] | int }}` when no variant
    is provided) are left as their original template string, so callers
    that only care about variant-independent entries can still proceed.
    """
    for key, value in context.items():
        if isinstance(value, str):
            with contextlib.suppress(UndefinedError):
                context[key] = jinja_env.from_string(value).render(context)

    return context


def _render_metadata_fields(
    section: dict[str, Any],
    fields: tuple[str, ...],
    env: jinja2.Environment,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a copy of `section` with named string fields rendered. Fields
    whose templates fail with UndefinedError are left as-is."""
    out = dict(section)
    for field in fields:
        value = out.get(field)
        if not isinstance(value, str):
            continue
        with contextlib.suppress(UndefinedError):
            out[field] = env.from_string(value).render(context)
    return out


def resolve_recipe_metadata(recipe_content: RecipeWithContext) -> dict[str, Any]:
    """
    Variant-free resolver for surface metadata (`name`, `version`, output
    package names). Substitutes simple `${{ name }}`-style references
    against the recipe's own `context:` section without rendering the
    full body, so variant-dependent context entries (e.g.
    `${{ (foo | split('.'))[1] | int }}`) don't crash the resolver.

    Use this when you need to read the recipe's identity before a variant
    matrix exists (e.g. for linting or pre-build metadata extraction).
    For full rendering, use `render_recipe_with_context` with a real
    `variant_config`.
    """
    env = jinja_env({})
    context = load_recipe_context(dict(recipe_content.get("context", {})), env)

    resolved: dict[str, Any] = dict(recipe_content)

    for section_key in ("package", "recipe"):
        section = resolved.get(section_key)
        if isinstance(section, dict):
            resolved[section_key] = _render_metadata_fields(section, ("name", "version"), env, context)

    outputs = resolved.get("outputs")
    if isinstance(outputs, list):
        new_outputs = []
        for output in outputs:
            if not isinstance(output, dict):
                new_outputs.append(output)
                continue
            new_output = _render_metadata_fields(output, ("name",), env, context)
            pkg = new_output.get("package")
            if isinstance(pkg, dict):
                new_output["package"] = _render_metadata_fields(pkg, ("name", "version"), env, context)
            new_outputs.append(new_output)
        resolved["outputs"] = new_outputs

    # Round-trip through YAML so callers receive ruamel CommentedMap/Seq
    # types matching what `render_recipe_with_context` used to return.
    return load_yaml(_dump_yaml_to_string(resolved))


def render_recipe_with_context(
    recipe_content: RecipeWithContext, variant_config: Mapping[str, str]
) -> dict[str, Any]:
    """
    Render the recipe using known values from context section.
    Unknown values are not evaluated and are kept as it is.

    `variant_config` is required: the recipe's `context:` may reference
    variant variables (target_platform, compiler runtimes, etc.) and Jinja
    expressions like `${{ (foo | split('.'))[1] | int }}` raise
    `UndefinedError` if their inputs are missing. Callers without a real
    variant matrix should not call this — extract `name`/`version`
    structurally instead.

    Examples:
    ---
    ```python
    >>> from pathlib import Path
    >>> from rattler_build_conda_compat.loader import load_yaml
    >>> recipe_content = load_yaml((Path().resolve() / "tests" / "data" / "eval_recipe_using_context.yaml").read_text())
    >>> evaluated_context = render_recipe_with_context(
    ...     recipe_content,
    ...     {"target_platform": "linux-64", "build_platform": "linux-64"},
    ... )
    >>> assert "my_value-${{ not_present_value }}" == evaluated_context["build"]["string"]
    >>>
    ```
    """
    env = jinja_env(variant_config)
    context = recipe_content.get("context", {})
    # render out the context section and retrieve dictionary
    context_variables = load_recipe_context(context, env)

    # render the rest of the document with the values from the context
    # and keep undefined expressions _as is_.
    template = env.from_string(_dump_yaml_to_string(recipe_content))
    rendered_content = template.render(context_variables)

    return load_yaml(rendered_content)
