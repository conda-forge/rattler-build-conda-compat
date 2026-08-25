from __future__ import annotations

import textwrap
from pathlib import Path

from rattler_build_conda_compat.jinja.filters import _version_to_build_string
from rattler_build_conda_compat.jinja.jinja import (
    jinja_env,
    load_recipe_context,
    render_recipe_with_context,
    resolve_recipe_metadata,
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


def test_load_recipe_context_keeps_variant_dependent_entries() -> None:
    recipe_yaml = load_yaml((test_data / "variant_context.yaml").read_text())
    context = recipe_yaml["context"]

    loaded_context = load_recipe_context(context, jinja_env())

    assert loaded_context["runtime_year"] == "2015"
    assert loaded_context["build_num"] == 34
    # entries that operate on variant variables cannot be evaluated without a
    # variant config and keep their original template string
    assert loaded_context["vc_major"] == '${{ (vcver | split(".")) [0] }}'
    assert loaded_context["vcvars_ver_maj"] == '${{ ((cl_version | split(".")) [0] | int) - 5 }}'


def test_render_recipe_with_context_keeps_variant_dependent_entries() -> None:
    """The context section must not be rendered a second time.

    `load_recipe_context` deliberately leaves entries it cannot evaluate -- those
    reading variant variables -- as raw template strings. Rendering the whole
    document afterwards, context section included, evaluates those same
    expressions again without that guard and raises `UndefinedError`.
    """
    recipe_yaml = load_yaml((test_data / "variant_context.yaml").read_text())

    rendered = render_recipe_with_context(recipe_yaml)

    # plain context values resolve throughout the document
    assert rendered["build"]["number"] == 34
    assert rendered["outputs"][1]["package"]["name"] == "vs2015_runtime"

    # variant-dependent ones stay templates instead of raising; callers such as
    # conda-smithy detect them with `"${{" in value` and skip the affected lints
    assert rendered["recipe"]["version"] == "${{ runtime_version }}"
    assert rendered["outputs"][0]["package"]["name"] == 'vcomp${{ (vcver | split(".")) [0] }}'

    # the returned context is the one `load_recipe_context` resolved
    assert rendered["context"]["runtime_year"] == "2015"
    assert rendered["context"]["vc_major"] == '${{ (vcver | split(".")) [0] }}'


def test_resolve_recipe_metadata_with_variant_dependent_context() -> None:
    recipe_yaml = load_yaml((test_data / "variant_context.yaml").read_text())

    resolved = resolve_recipe_metadata(recipe_yaml)

    assert resolved["recipe"]["name"] == "vc-feedstock"
    # version depends on a variant variable and stays a template
    assert resolved["recipe"]["version"] == "${{ runtime_version }}"
    outputs = resolved["outputs"]
    # vc_major is variant-dependent, so the name stays a template
    assert outputs[0]["package"]["name"] == "vcomp${{ vc_major }}"
    # runtime_year is a plain context value and resolves
    assert outputs[1]["package"]["name"] == "vs2015_runtime"


def test_resolve_recipe_metadata_single_output() -> None:
    recipe_yaml = load_yaml((test_data / "context.yaml").read_text())

    resolved = resolve_recipe_metadata(recipe_yaml)

    assert resolved["package"]["name"] == "foo"
    assert resolved["package"]["version"] == "bla"


def test_load_recipe_context() -> None:
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
        "big_folded_string": "A big string on a lot of lines",
        "big_pipe_string": "A big string\non a lot of lines",
        "big_dq_flow_string": "A big string\non a \"lot\" 'of' lines",
        "big_flow_string": "A big string\non a lot of lines",
        "big_sq_flow_string": "A big string\non a \"lot\" 'of' lines",
        "big_pipe_string_minus": "A big string\non a lot of lines",
        "big_pipe_string_plus": "A big string\non a lot of lines\n\n",
        "big_folded_string_minus": "A big string on a lot of lines",
        "big_folded_string_plus": "A big string on a lot of lines\n\n",
    }
