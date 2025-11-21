from pathlib import Path

from rattler_build_conda_compat import yaml
from rattler_build_conda_compat.loader import load_yaml
from rattler_build_conda_compat.recipe_sources import render_all_sources
from rattler_build_conda_compat.utils import has_recipe


def test_recipe_is_present(recipe_dir) -> None:
    assert has_recipe(recipe_dir)


def test_recipe_is_absent(old_recipe_dir) -> None:
    assert has_recipe(old_recipe_dir) is False


def test_cbc_to_yaml() -> None:
    # loaded from conda-build config (e.g. in conda-smithy),
    # all values are cast to strings
    cbc = {
        "bool": ["true", "false"],
        "int": ["4", "5"],
    }
    # serializing should return booleans to to actual bools
    cbc_yaml = yaml._dump_yaml_to_string(cbc)
    rt = yaml._yaml_object().load(cbc_yaml)
    assert rt == {
        "bool": [True, False],
        "int": ["4", "5"],
    }


def test_render_all_sources() -> None:
    recipe = Path("tests/data/polars_recipe.yaml")
    recipe_yaml = load_yaml(recipe.read_text())

    variants = [
        {"polars_runtime": ["32"], "target_platform": ["linux-64"]},
        {"polars_runtime": ["64"], "target_platform": ["linux-64"]},
        {"polars_runtime": ["compat"], "target_platform": ["linux-64"]},
    ]

    sources = render_all_sources(recipe=recipe_yaml, variants=variants)

    urls: set[str] = set()
    for source in sources:
        url = source.url
        assert isinstance(url, str)
        urls.add(url)

    assert urls == {
        "https://pypi.org/packages/source/p/polars/polars-1.35.1.tar.gz",
        "https://pypi.org/packages/source/p/polars-runtime-32/polars_runtime_32-1.35.1.tar.gz",
        "https://pypi.org/packages/source/p/polars-runtime-64/polars_runtime_64-1.35.1.tar.gz",
        "https://pypi.org/packages/source/p/polars-runtime-compat/polars_runtime_compat-1.35.1.tar.gz",
    }
