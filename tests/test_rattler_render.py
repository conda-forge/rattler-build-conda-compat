from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rattler_build_conda_compat.loader import parse_recipe_config_file
from rattler_build_conda_compat.render import MetaData, render

if TYPE_CHECKING:
    from pathlib import Path


def test_render_recipe(python_recipe: Path, unix_namespace: dict[str, Any], snapshot) -> None:
    variants = parse_recipe_config_file(str(python_recipe / "variants.yaml"), unix_namespace)

    rendered = render(str(python_recipe), variants=variants, platform="linux", arch="64")

    all_used_variants = [meta[0].get_used_variant() for meta in rendered]

    assert len(all_used_variants) == 4

    assert snapshot == all_used_variants


def test_environ_is_passed_to_rattler_build(env_recipe, snapshot) -> None:
    try:
        os.environ["TEST_SHOULD_BE_PASSED"] = "false"
        rendered = render(str(env_recipe), platform="linux", arch="64")
        all_used_variants = [meta[0].meta for meta in rendered]
        assert len(all_used_variants) == 1
        # for this scenario recipe should not be rendered
        assert snapshot == all_used_variants

        os.environ["TEST_SHOULD_BE_PASSED"] = "true"

        rendered = render(str(env_recipe), platform="linux", arch="64")

        all_used_variants = [meta[0].meta for meta in rendered]
        assert len(all_used_variants) == 1
        # for this scenario recipe should be rendered
        assert snapshot == all_used_variants[0]["build_configuration"]["variant"]

    finally:
        os.environ.pop("TEST_SHOULD_BE_PASSED", None)


def test_metadata_for_single_output(feedstock_dir_with_recipe: Path, rich_recipe: Path) -> None:
    (feedstock_dir_with_recipe / "recipe" / "recipe.yaml").write_text(
        rich_recipe.read_text(), encoding="utf8"
    )

    rattler_metadata = MetaData(feedstock_dir_with_recipe)

    assert rattler_metadata.name() == "rich"
    assert rattler_metadata.version() == "13.4.2"
    assert rattler_metadata.dist() == "rich-13.4.2-unrendered_0"


def test_metadata_for_multiple_output(feedstock_dir_with_recipe: Path, mamba_recipe: Path) -> None:
    (feedstock_dir_with_recipe / "recipe" / "recipe.yaml").write_text(
        mamba_recipe.read_text(), encoding="utf8"
    )

    rattler_metadata = MetaData(feedstock_dir_with_recipe)

    assert rattler_metadata.name() == "mamba-split"
    assert rattler_metadata.version() == "1.5.8"


def test_metadata_when_rendering_single_output(
    feedstock_dir_with_recipe: Path, rich_recipe: Path
) -> None:
    recipe_path = feedstock_dir_with_recipe / "recipe" / "recipe.yaml"
    (recipe_path).write_text(rich_recipe.read_text(), encoding="utf8")

    rendered = render(str(recipe_path), platform="linux", arch="64")
    meta = rendered[0][0]
    assert meta.name() == "rich"
    assert meta.version() == "13.4.2"
    dist = meta.dist()
    dist_name, dist_version, build_id = dist.split("-")
    assert dist_name == meta.name()
    assert dist_version == meta.version()
    assert build_id.startswith("pyh")
    assert build_id.endswith("_0")


def test_metadata_when_rendering_multiple_output(
    feedstock_dir_with_recipe: Path, multiple_outputs: Path
) -> None:
    recipe_path = feedstock_dir_with_recipe / "recipe" / "recipe.yaml"
    (recipe_path).write_text(multiple_outputs.read_text(), encoding="utf8")

    rendered = render(str(recipe_path), platform="linux", arch="64")

    assert rendered[0][0].name() == "libmamba"
    assert rendered[0][0].version() == "1.5.8"


def test_used_variant(feedstock_dir_with_recipe: Path, multiple_outputs: Path) -> None:
    recipe_path = feedstock_dir_with_recipe / "recipe" / "recipe.yaml"
    (recipe_path).write_text(multiple_outputs.read_text(), encoding="utf8")

    # e.g. conda-forge, variant file may include variants
    # on outputs from the given package
    variants = {
        "libmamba": ["1", "2"],
        "unused": "scalar",
        "python": ["3.12", "3.13"],
    }
    rendered = render(str(recipe_path), variants=variants, platform="linux", arch="64")
    # 3 outputs, 2 of which use python
    assert len(rendered) == 5
    meta = rendered[-1][0]
    assert "libmamba" not in meta.get_used_vars()
    assert "libmamba" not in meta.get_used_variant()
    assert "python" in meta.get_used_variant()
    assert "python" in meta.get_used_variant()

    # make sure unused variants are still in the variant dicts,
    # but reduced to first scalar
    assert "libmamba" in meta.config.variant
    for variant in meta.config.variants:
        assert variant["libmamba"] == "1"

    assert "unused" in meta.config.variant


def test_bool_roundtrip(feedstock_dir_with_recipe: Path, py_abi3_recipe: Path) -> None:
    recipe_path = feedstock_dir_with_recipe / "recipe" / "recipe.yaml"
    (recipe_path).write_text(py_abi3_recipe.read_text(), encoding="utf8")

    # conda-build variants are all always strings
    # booleans 'true' and 'false' should be treated as bools
    # during render, but still return conda-build-style string values in used variant dict
    variants = {
        "is_abi3": ["true", "false"],
        "python": ["3.12", "3.13"],
        "zip_keys": [
            ["python", "is_abi3"],
        ],
    }
    rendered = render(str(recipe_path), variants=variants, platform="linux", arch="64")
    # 2 outputs, one is_abi3=true, one is_abi3=false
    assert len(rendered) == 2
    meta_abi3, meta_noabi3 = rendered[0][0], rendered[1][0]
    # make sure result is still conda-build-style string
    assert meta_abi3.get_used_variant()["is_abi3"] == "true"
    assert meta_noabi3.get_used_variant()["is_abi3"] == "false"

    # make sure it was treated as a bool during render
    assert meta_abi3.meta["build_configuration"]["variant"]["is_abi3"] is True
    assert meta_noabi3.meta["build_configuration"]["variant"]["is_abi3"] is False
    assert "python-abi3" in meta_abi3.meta["recipe"]["requirements"]["host"]
    assert "python-abi3" not in meta_noabi3.meta["recipe"]["requirements"]["host"]
