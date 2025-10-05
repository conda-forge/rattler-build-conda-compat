from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

import jinja2
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

if TYPE_CHECKING:
    from collections.abc import Mapping


class RecipeWithContext(TypedDict, total=False):
    context: dict[str, str]


def jinja_env(variant_config: Mapping[str, str] | None = None) -> SandboxedEnvironment:
    """
    Create a `rattler-build` specific Jinja2 environment with modified syntax.
    Target platform, build platform, and mpi are set to linux-64 by default.
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

    # inject rattler-build recipe functions in jinja environment
    if not variant_config:
        variant_config = {"target_platform": "linux-64", "build_platform": "linux-64", "mpi": "mpi"}

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
    Use linux-64 as default target_platform, build_platform, and mpi.
    """
    # Process each key-value pair in the dictionary
    for key, value in context.items():
        # If the value is a string, render it as a template
        if isinstance(value, str):
            template = jinja_env.from_string(value)
            rendered_value = template.render(context)
            context[key] = load_yaml("value: " + rendered_value)["value"]

    return context


def render_recipe_with_context(
    recipe_content: RecipeWithContext, variant_config: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """
    Render the recipe using known values from context section.
    Unknown values are not evaluated and are kept as it is.
    Target platform, build platform, and mpi are set to linux-64 by default.

    Examples:
    ---
    ```python
    >>> from pathlib import Path
    >>> from rattler_build_conda_compat.loader import load_yaml
    >>> recipe_content = load_yaml((Path().resolve() / "tests" / "data" / "eval_recipe_using_context.yaml").read_text())
    >>> evaluated_context = render_recipe_with_context(recipe_content)
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
