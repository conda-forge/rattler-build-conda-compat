from __future__ import annotations

import textwrap
from pathlib import Path

from rattler_build_conda_compat.jinja.jinja import (
    render_recipe_with_context,
)
from rattler_build_conda_compat.loader import load_yaml
from rattler_build_conda_compat.yaml import _dump_yaml_to_string, _yaml_object

test_data = Path(__file__).parent / "data"


def test_render_recipe_with_context(snapshot) -> None:
    recipe = Path("tests/data/mamba_recipe.yaml")
    recipe_yaml = load_yaml(recipe.read_text())

    rendered = render_recipe_with_context(recipe_yaml)
    into_yaml = _dump_yaml_to_string(rendered)

    assert into_yaml == snapshot


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


def test_render_recipe_with_context_variant_dependent_entries() -> None:
    """Recipes like vc-feedstock compute context values from variant variables
    (e.g. ``${{ (vcver | split(".")) [0] }}``) that are only known once a
    variant config exists. Rendering must keep those templates verbatim.
    """
    recipe_yaml = load_yaml((test_data / "variant_context.yaml").read_text())

    rendered = render_recipe_with_context(recipe_yaml)

    context = rendered["context"]
    assert context["runtime_year"] == "2015"
    assert context["build_num"] == 34
    # entries that operate on variant variables cannot be evaluated without a
    # variant config and keep their original template string
    assert context["vc_major"] == '${{ (vcver | split(".")) [0] }}'
    assert context["vcvars_ver_maj"] == '${{ ((cl_version | split(".")) [0] | int) - 5 }}'
    # references to unresolved entries stay verbatim as well
    assert context["vcvars_ver"] == "${{ vcvars_ver_maj }}.${{ vcvars_ver_min }}"

    assert rendered["recipe"]["name"] == "vc-feedstock"
    # version depends on a variant variable and stays a template
    assert rendered["recipe"]["version"] == "${{ runtime_version }}"
    outputs = rendered["outputs"]
    # vc_major is variant-dependent, so the name stays a template
    assert outputs[0]["package"]["name"] == "vcomp${{ vc_major }}"
    # runtime_year is a plain context value and resolves
    assert outputs[1]["package"]["name"] == "vs2015_runtime"
    assert rendered["build"]["number"] == 34


def test_render_recipe_with_context_context_section() -> None:
    context_str = textwrap.dedent(
        r"""
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
          big_pipe_string: |
            A big string
            on a lot of lines
          big_folded_string: >
            A big string
            on a lot of lines
          big_flow_string: A big string

            on a lot of lines
          big_sq_flow_string: 'A big string

            on a "lot" ''of'' lines'
          big_dq_flow_string: "A big string

            on a \"lot\" 'of' lines"
          big_pipe_string_plus: |+
            A big string
            on a lot of lines


          big_pipe_string_minus: |-
            A big string
            on a lot of lines
          big_folded_string_plus: >+
            A big string
            on a lot of lines


          big_folded_string_minus: >-
            A big string
            on a lot of lines



        """
    )
    recipe = _yaml_object().load(context_str)

    rendered_context = render_recipe_with_context(recipe)["context"]
    assert rendered_context == {
        "version": "0.2025.39",
        "name": "stackvana-core",
        "dm_tag": "w_2025_39",
        "non_weekly_dm_tag": "v0_2025_39",
        "patch_version": "_39",
        # fully resolved scalars are re-typed the way YAML would read them back
        "raw_major_version": 0,
        "raw_minor_version": 2025,
        "raw_patch_version": 39,
        "weekly_dm_tag": "w_2025_39",
        "raw_minor_version_ml": 2025,
        "raw_minor_version_int": 2025,
        # untemplated strings pass through untouched, so block scalars keep
        # their trailing newlines
        "big_folded_string": "A big string on a lot of lines\n",
        "big_pipe_string": "A big string\non a lot of lines\n",
        "big_dq_flow_string": "A big string\non a \"lot\" 'of' lines",
        "big_flow_string": "A big string\non a lot of lines",
        "big_sq_flow_string": "A big string\non a \"lot\" 'of' lines",
        "big_pipe_string_minus": "A big string\non a lot of lines",
        "big_pipe_string_plus": "A big string\non a lot of lines\n\n\n",
        "big_folded_string_minus": "A big string on a lot of lines",
        "big_folded_string_plus": "A big string on a lot of lines\n\n\n",
    }
