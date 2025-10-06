from __future__ import annotations

import textwrap
from pathlib import Path

from rattler_build_conda_compat.jinja.filters import _version_to_build_string
from rattler_build_conda_compat.jinja.jinja import (
    jinja_env,
    load_recipe_context,
    render_recipe_with_context,
)
from rattler_build_conda_compat.jinja.utils import _MissingUndefined
from rattler_build_conda_compat.loader import load_yaml
from rattler_build_conda_compat.yaml import _dump_yaml_to_string, _yaml_object

test_data = Path(__file__).parent / "data"


def test_render_recipe_with_context(snapshot) -> None:
    recipe = Path("tests/data/mamba_recipe.yaml")
    recipe_yaml = load_yaml(recipe.read_text())

    rendered = render_recipe_with_context(recipe_yaml)
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

    rendered = render_recipe_with_context(recipe_yaml)
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


def test_load_recipe_context() -> None:
    context_str = textwrap.dedent(
        """
        context:
          name: stackvana-core
          version: 0.2025.39
          raw_major_version: '${{ (version | split("."))[0] }}'
          raw_minor_version: '${{ (version | split("."))[1] }}'
          raw_minor_version_ml: |
            ${{ (version | split("."))[1] }}  # this one is an int
          raw_minor_version_int: ${{ (version | split("."))[1] }}  # this one is an int too
          raw_patch_version: '${{ (version | split("."))[2] }}'
          patch_version: ${{ "_" + raw_patch_version if (raw_patch_version | length) == 2 else "_0"  + raw_patch_version }}
          weekly_dm_tag: ${{ "w_" + raw_minor_version + patch_version }}
          non_weekly_dm_tag: ${{ "v" + (version | replace(".", "_")) }}
          dm_tag: ${{ weekly_dm_tag if raw_major_version == '0' else non_weekly_dm_tag }}
        """
    )
    context = _yaml_object().load(context_str)["context"]

    loaded_context = load_recipe_context(context, jinja_env())
    assert loaded_context == {
        "version": "0.2025.39",
        "name": "stackvana-core",
        "dm_tag": "w_2025_39",
        "non_weekly_dm_tag": "v0_2025_39",
        "patch_version": "_39",
        "raw_major_version": "0",
        "raw_minor_version": "2025",
        "raw_patch_version": "39",
        "weekly_dm_tag": "w_2025_39",
        "raw_minor_version_ml": 2025,
        "raw_minor_version_int": 2025,
    }
