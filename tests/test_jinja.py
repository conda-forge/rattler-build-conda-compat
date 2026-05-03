from __future__ import annotations

from pathlib import Path

from rattler_build_conda_compat.jinja.filters import _version_to_build_string
from rattler_build_conda_compat.jinja.jinja import render_recipe_with_context
from rattler_build_conda_compat.jinja.utils import _MissingUndefined
from rattler_build_conda_compat.loader import load_yaml
from rattler_build_conda_compat.yaml import _dump_yaml_to_string

test_data = Path(__file__).parent / "data"


_DEFAULT_VARIANT = {
    "target_platform": "linux-64",
    "build_platform": "linux-64",
    "mpi": "mpi",
}


def test_render_recipe_with_context(snapshot) -> None:
    recipe = Path("tests/data/mamba_recipe.yaml")
    recipe_yaml = load_yaml(recipe.read_text())

    rendered = render_recipe_with_context(recipe_yaml, _DEFAULT_VARIANT)
    into_yaml = _dump_yaml_to_string(rendered)

    assert into_yaml == snapshot


def test_version_to_build_string() -> None:
    assert _version_to_build_string("1.2.3") == "12"
    assert _version_to_build_string("1.2") == "12"
    assert _version_to_build_string("nothing") == "nothing"
    some_undefined = _MissingUndefined(name="python")
    assert _version_to_build_string(some_undefined) == "python_version_to_build_string"


def test_context_rendering(snapshot) -> None:
    recipe = test_data / "context.yaml"

    recipe_yaml = load_yaml(recipe.read_text())

    rendered = render_recipe_with_context(recipe_yaml, _DEFAULT_VARIANT)
    into_yaml = _dump_yaml_to_string(rendered)

    assert into_yaml == snapshot

    jolt_physics = test_data / "jolt-physics" / "recipe.yaml"
    variants = (test_data / "jolt-physics" / "ci_support").glob("*.yaml")

    recipe_yaml = load_yaml(jolt_physics.read_text())
    variants = [load_yaml(variant.read_text()) for variant in variants]

    rendered = []
    for v in variants:
        vx = {el: v[el][0] for el in v}

        rendered.append(render_recipe_with_context(recipe_yaml, vx))

    into_yaml = _dump_yaml_to_string(rendered)

    assert into_yaml == snapshot
