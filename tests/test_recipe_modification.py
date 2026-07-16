from pathlib import Path

import pytest

from rattler_build_conda_compat.modify_recipe import (
    CouldNotUpdateVersionError,
    update_build_number,
    update_version,
)


def test_build_number_mod(data_dir: Path) -> None:
    tests = data_dir / "build_number"
    result = update_build_number(tests / "test_1/recipe.yaml", 0)
    expected = tests / "test_1/expected.yaml"
    assert result == expected.read_text()

    result = update_build_number(tests / "test_2/recipe.yaml", 0)
    expected = tests / "test_2/expected.yaml"
    assert result == expected.read_text()


def test_version_mod(data_dir: Path) -> None:
    tests = data_dir / "version"
    test_recipes = [tests / "test_1/recipe.yaml", tests / "test_2/recipe.yaml"]
    for recipe in test_recipes:
        result = update_version(recipe, "0.25.0", None)
        expected = recipe.parent / "expected.yaml"
        assert result == expected.read_text()

    test_python = tests / "test_3/recipe.yaml"
    result = update_version(test_python, "1.9.0", None)
    expected = test_python.parent / "expected.yaml"
    assert result == expected.read_text()

    test_cran = tests / "test_4/recipe.yaml"
    result = update_version(test_cran, "1.1-30", None)
    expected = test_cran.parent / "expected.yaml"
    assert result == expected.read_text()


def test_version_mod_aborts_on_unresolved_url(tmp_path: Path) -> None:
    """A source URL that still holds an unresolved expression after rendering
    must abort the bump rather than get downloaded: hashing an error page would
    write a plausible-looking but wrong sha256 into the feedstock.
    """
    recipe = tmp_path / "recipe.yaml"
    recipe.write_text(
        """
context:
  version: "1.0"
package:
  name: test
  version: ${{ version }}
source:
  url: https://foo.com/${{ name_var }}-${{ version }}.tar.gz
  sha256: 0000000000000000000000000000000000000000000000000000000000000000
""",
        encoding="utf-8",
    )
    with pytest.raises(CouldNotUpdateVersionError, match="Could not fully render the source URL"):
        update_version(recipe, "2.0", None)


def test_multi_source(data_dir: Path) -> None:
    tests = data_dir / "version"
    test_recipe = tests / "embree/recipe.yaml"
    result = update_version(test_recipe, "3.7.0", None)
    expected = test_recipe.parent / "expected.yaml"
    assert result == expected.read_text()


def test_mpich(data_dir: Path) -> None:
    tests = data_dir / "version"
    test_recipe = tests / "mpich/recipe.yaml"
    result = update_version(test_recipe, "4.1.1", None)
    print(result)
    expected = test_recipe.parent / "expected.yaml"
    assert result == expected.read_text()
