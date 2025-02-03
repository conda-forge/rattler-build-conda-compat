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

    assert rendered[0][0].name() == "rich"
    assert rendered[0][0].version() == "13.4.2"


def test_metadata_when_rendering_multiple_output(
    feedstock_dir_with_recipe: Path, multiple_outputs: Path
) -> None:
    recipe_path = feedstock_dir_with_recipe / "recipe" / "recipe.yaml"
    (recipe_path).write_text(multiple_outputs.read_text(), encoding="utf8")

    rendered = render(str(recipe_path), platform="linux", arch="64")

    assert rendered[0][0].name() == "libmamba"
    assert rendered[0][0].version() == "1.5.8"
