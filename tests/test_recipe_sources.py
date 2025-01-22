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


def test_variant_variables_source_render(snapshot) -> None:
    polars = test_data / "polars" / "sources.yaml"
    variants = (test_data / "polars" / "ci_support").glob("*.yaml")

    recipe_yaml = load_yaml(polars.read_text())
    variants = [load_yaml(variant.read_text()) for variant in variants]

    sources = render_all_sources(recipe_yaml, variants)
    assert sources == snapshot
