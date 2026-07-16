from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from rattler_build.jinja_config import JinjaConfig
from rattler_build.render import render_context
from rattler_build.tool_config import PlatformConfig

from rattler_build_conda_compat.jinja.objects import (
    _stub_compatible_pin,
    _stub_match,
    _stub_subpackage_pin,
)
from rattler_build_conda_compat.loader import load_yaml
from rattler_build_conda_compat.yaml import _dump_yaml_to_string

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


class RecipeWithContext(TypedDict, total=False):
    context: dict[str, str]


DEFAULT_VARIANT_CONFIG: dict[str, str] = {
    "target_platform": "linux-64",
    "build_platform": "linux-64",
    "mpi": "mpi",
}


def _stub_functions() -> dict[str, Callable[..., str]]:
    """
    Stub implementations of rattler-build's build-phase helper functions.
    They produce the placeholder strings conda-smithy's linter matches on
    (e.g. ``c_compiler_stub``, ``subpackage_pin foo``) without requiring
    build-time information.
    """
    return {
        "compiler": lambda x: f"{x}_compiler_stub",
        "stdlib": lambda x: f"{x}_stdlib_stub",
        "pin_subpackage": _stub_subpackage_pin,
        "pin_compatible": _stub_compatible_pin,
        "cdt": lambda *args, **kwargs: "cdt_stub",  # noqa: ARG005
        "match": _stub_match,
    }


def jinja_config(variant_config: Mapping[str, Any] | None = None) -> JinjaConfig:
    """
    Create a rattler-build Jinja configuration from a variant mapping.
    Target platform, build platform, and mpi are set to linux-64 by default.
    """
    if not variant_config:
        variant_config = DEFAULT_VARIANT_CONFIG

    platform = PlatformConfig(
        target_platform=str(variant_config.get("target_platform", "linux-64")),
        build_platform=str(variant_config.get("build_platform", "linux-64")),
    )
    return JinjaConfig(platform=platform, variant=dict(variant_config))


def render_recipe_with_context(
    recipe_content: RecipeWithContext, variant_config: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """
    Render the recipe using known values from context section.
    Unknown values are not evaluated and are kept as they are.
    Build-phase helper functions (``compiler``, ``pin_subpackage``, ...) render
    to stub placeholders. Target platform, build platform, and mpi are set to
    linux-64 by default.

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
    rendered = render_context(
        dict(recipe_content), jinja_config(variant_config), functions=_stub_functions()
    )

    # dump and reload so the result consists of the same ruamel.yaml types that
    # loading the rendered recipe from disk would produce
    return load_yaml(_dump_yaml_to_string(rendered))  # type: ignore[no-any-return]
