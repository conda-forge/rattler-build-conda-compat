"""Contract tests for the API surface conda-smithy depends on.

conda-smithy's linter matches on the exact placeholder strings produced by
``render_recipe_with_context`` (e.g. ``c_compiler_stub`` in
``linter/hints.py``, the ``compatible_pin ``/``subpackage_pin `` prefixes in
``linter/lints.py``) and reads specific keys from ``MetaData.meta``. These
tests pin those behaviors so a change in the underlying renderer fails here
before it reaches a release.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rattler_build_conda_compat.jinja.jinja import render_recipe_with_context
from rattler_build_conda_compat.loader import load_yaml
from rattler_build_conda_compat.render import render


def _render_requirement(requirement: str) -> str:
    recipe = load_yaml(
        f"""
        package:
          name: contract
          version: "1.0"
        requirements:
          build:
            - {requirement}
        """
    )
    rendered = render_recipe_with_context(recipe)
    return str(rendered["requirements"]["build"][0])


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        # conda_smithy/linter/hints.py matches on the `_compiler_stub` suffix
        ("${{ compiler('c') }}", "c_compiler_stub"),
        ("${{ compiler('cxx') }}", "cxx_compiler_stub"),
        ("${{ compiler('fortran') }}", "fortran_compiler_stub"),
        ("${{ compiler('rust') }}", "rust_compiler_stub"),
        ("${{ compiler('go-cgo') }}", "go-cgo_compiler_stub"),
        ("${{ compiler('m2w64_c') }}", "m2w64_c_compiler_stub"),
        ("${{ stdlib('c') }}", "c_stdlib_stub"),
        ("${{ stdlib('m2w64_c') }}", "m2w64_c_stdlib_stub"),
        # conda_smithy/linter/lints.py filters on the `subpackage_pin ` and
        # `compatible_pin ` prefixes
        ("${{ pin_subpackage('libfoo') }}", "subpackage_pin libfoo"),
        (
            "${{ pin_subpackage('libfoo', exact=True) }}",
            "subpackage_pin libfoo",
        ),
        (
            "${{ pin_compatible('numpy', upper_bound='x.x') }}",
            "compatible_pin numpy",
        ),
        ("${{ cdt('mesa-libgl-devel') }}", "cdt_stub"),
    ],
)
def test_stub_strings(requirement: str, expected: str) -> None:
    assert _render_requirement(requirement) == expected


@pytest.mark.parametrize(
    "requirement",
    [
        "${{ some_undefined_thing }}",
        # `env` is not resolvable at lint time and must not leak host
        # environment variables into the rendered recipe
        "${{ env.get('SOME_VARIABLE') }}",
        # helpers whose argument is an unresolved variable stay verbatim;
        # conda-smithy skips requirement entries containing `{{`, so these
        # never reach its MatchSpec validation
        "${{ match(python, '>=3.10') }}",
        "${{ pin_subpackage(some_name_variable) }}",
        "${{ compiler(compiler_variable) }}",
    ],
)
def test_undefined_expressions_stay_verbatim(requirement: str) -> None:
    """Expressions that cannot be resolved keep their original template text."""
    assert _render_requirement(requirement) == requirement


def test_render_context_preserves_conditional_source_structure() -> None:
    """The compat layer pairs the raw recipe tree with the rendered tree
    node-by-node: ``_retype_rendered_scalars`` recovers scalar types, and
    ``recipe_sources``/``modify_recipe`` ``zip(..., strict=True)`` the raw and
    rendered source lists. That only holds because ``render_context`` never
    changes the document shape -- in particular it must not collapse an
    ``if/then/else`` source into its chosen branch. If a future py-rattler-build
    starts evaluating selectors while rendering context, the source counts
    diverge and the strict zips raise; pinning it here surfaces that on a bump
    instead of on a real feedstock's version update.
    """
    recipe = load_yaml(
        """
        context:
          version: "1.0"
        package:
          name: contract
          version: ${{ version }}
        source:
          - if: unix
            then:
              url: https://foo.com/unix-${{ version }}.tar.gz
            else:
              url: https://foo.com/win-${{ version }}.tar.gz
        """
    )
    rendered = render_recipe_with_context(recipe)

    source = rendered["source"]
    assert isinstance(source, list)
    assert len(source) == 1
    # the conditional is kept verbatim, not resolved into a single branch
    conditional = source[0]
    assert set(conditional) == {"if", "then", "else"}
    assert conditional["if"] == "unix"
    # templated values inside the branches are still substituted
    assert conditional["then"]["url"] == "https://foo.com/unix-1.0.tar.gz"
    assert conditional["else"]["url"] == "https://foo.com/win-1.0.tar.gz"


def test_platform_variables_from_variant_config() -> None:
    """Platform shortcut variables derive from the variant target_platform."""
    recipe = load_yaml(
        """
        package:
          name: contract
          version: "1.0"
        build:
          skip: ${{ win }}
        """
    )
    rendered = render_recipe_with_context(recipe, {"target_platform": "win-64"})
    assert rendered["build"]["skip"] is True

    rendered = render_recipe_with_context(recipe, {"target_platform": "linux-64"})
    assert rendered["build"]["skip"] is False


def test_quoted_scalars_stay_strings() -> None:
    """Substituted values keep their YAML quoting semantics: a quoted usage
    site stays a string ("3.10" must not become the float-ish "3.1"), while
    an unquoted usage site is re-read the way YAML would read the rendered
    recipe from disk.
    """
    recipe = load_yaml(
        """
        context:
          python_min: "3.10"
          build_num: 5
        package:
          name: x
          version: "1.0"
        build:
          number: ${{ build_num }}
        tests:
          - python:
              python_version: "${{ python_min }}"
          - script:
              - echo ${{ python_min }}
        """
    )
    rendered = render_recipe_with_context(recipe)

    assert rendered["context"]["python_min"] == "3.10"
    assert rendered["tests"][0]["python"]["python_version"] == "3.10"
    # unquoted usage embedded in a longer string stays textual
    assert rendered["tests"][1]["script"][0] == "echo 3.10"
    # unquoted numeric substitution is re-read as an int, like a rendered
    # recipe file would be
    assert rendered["build"]["number"] == 5


def test_metadata_meta_shape(feedstock_dir_with_recipe: Path, rich_recipe: Path) -> None:
    """conda-smithy reads these keys from ``MetaData.meta`` after rendering
    (``conda_smithy/configure_feedstock.py`` and ``MetaData.get_used_vars``).
    """
    recipe_path = feedstock_dir_with_recipe / "recipe" / "recipe.yaml"
    recipe_path.write_text(rich_recipe.read_text(), encoding="utf8")

    rendered = render(str(recipe_path), platform="linux", arch="64")

    meta = rendered[0][0].meta
    assert "recipe" in meta
    assert "package" in meta["recipe"]
    build_configuration = meta["build_configuration"]
    assert isinstance(build_configuration["variant"], dict)
    assert "subpackages" in build_configuration
