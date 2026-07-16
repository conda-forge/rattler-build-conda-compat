from __future__ import annotations

from pathlib import Path

import pytest

from rattler_build_conda_compat.loader import load_yaml
from rattler_build_conda_compat.recipe_sources import get_all_url_sources, render_all_sources

test_data = Path(__file__).parent / "data"


@pytest.mark.parametrize(
    ("partial_recipe", "expected_output"),
    [
        ("single_source.yaml", ["https://foo.com"]),
        ("multiple_sources.yaml", ["https://foo.com", "https://bar.com"]),
        ("if_then_source.yaml", ["https://foo.com", "https://bar.com"]),
        (
            "outputs_source.yaml",
            ["https://foo.com", "https://bar.com", "https://baz.com", "https://qux.com"],
        ),
        (
            "staging_outputs.yaml",
            ["https://example.com/libfoo-${{ version }}.tar.gz"],
        ),
    ],
)
def test_recipe_sources(partial_recipe: str, expected_output: list[str]) -> None:
    """Test that the recipe sources are correctly extracted from the recipe"""
    path = Path(f"{Path(__file__).parent}/data/{partial_recipe}")
    recipe = load_yaml(path.read_text())
    assert list(get_all_url_sources(recipe)) == expected_output


def test_multi_source_render(snapshot) -> None:
    jolt_physics = test_data / "jolt-physics" / "sources.yaml"
    variants = (test_data / "jolt-physics" / "ci_support").glob("*.yaml")

    recipe_yaml = load_yaml(jolt_physics.read_text())
    variants = [load_yaml(variant.read_text()) for variant in variants]

    sources = render_all_sources(recipe_yaml, variants)
    assert sources == snapshot


def test_conditional_source_render(snapshot) -> None:
    jolt_physics = test_data / "conditional_sources.yaml"
    # reuse the ci_support variants
    variants = (test_data / "jolt-physics" / "ci_support").glob("*.yaml")

    recipe_yaml = load_yaml(jolt_physics.read_text())
    variants = [load_yaml(variant.read_text()) for variant in variants]

    sources = render_all_sources(recipe_yaml, variants)
    assert len(sources) == 4
    assert sources == snapshot


def test_outputs_only_source_render(snapshot) -> None:
    outputs_only = test_data / "outputs_only_sources.yaml"

    recipe_yaml = load_yaml(outputs_only.read_text())
    variants: list[dict[str, list[str]]] = [{}]

    sources = render_all_sources(recipe_yaml, variants)
    assert len(sources) == 3
    assert sources == snapshot


def test_cache_source_render() -> None:
    """Sources in the `cache:` section render alongside output sources."""
    recipe_yaml = load_yaml((test_data / "cache_sources.yaml").read_text())

    sources = render_all_sources(recipe_yaml, [{}])

    urls = sorted(str(source.url) for source in sources)
    assert urls == [
        "https://cache.com/foo-1.2.3.tar.gz",
        "https://outputs.com/foo-core-1.2.3.zip",
    ]


def test_list_url_source_render() -> None:
    """A source with a list of mirror URLs renders every entry and keeps the raw templates."""
    recipe_yaml = load_yaml((test_data / "mirror_sources.yaml").read_text())

    sources = render_all_sources(recipe_yaml, [{}])

    assert len(sources) == 1
    source = next(iter(sources))
    assert source.url == [
        "https://mirror1.com/pkg-2.0.tar.gz",
        "https://mirror2.com/pkg-2.0.tar.gz",
    ]
    assert source.template == [
        "https://mirror1.com/pkg-${{ version }}.tar.gz",
        "https://mirror2.com/pkg-${{ version }}.tar.gz",
    ]


def test_variant_value_selector_render() -> None:
    """`if:` selectors comparing variant variable values pick the matching branch per combination."""
    recipe_yaml = load_yaml((test_data / "variant_selector_sources.yaml").read_text())
    variants: list[dict[str, list[str]]] = [{"blas_impl": ["mkl", "openblas"]}]

    sources = render_all_sources(recipe_yaml, variants)

    urls = sorted(str(source.url) for source in sources)
    assert urls == [
        "https://foo.com/mkl-1.0.tar.gz",
        "https://foo.com/openblas-1.0.tar.gz",
    ]


def test_variant_variables_source_render(snapshot) -> None:
    polars = test_data / "polars" / "sources.yaml"
    variants = (test_data / "polars" / "ci_support").glob("*.yaml")

    recipe_yaml = load_yaml(polars.read_text())
    variants = [load_yaml(variant.read_text()) for variant in variants]

    sources = render_all_sources(recipe_yaml, variants)
    assert sources == snapshot
