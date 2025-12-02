from __future__ import annotations

from pathlib import Path
from typing import Any

from rattler_build_conda_compat.loader import (
    load_all_requirements,
    load_all_tests,
    load_yaml,
    parse_recipe_config_file,
)


def test_load_variants(snapshot, unix_namespace: dict[str, Any]) -> None:
    variants_path = Path("tests/data/variants.yaml")

    loaded_variants = parse_recipe_config_file(str(variants_path), unix_namespace)

    assert loaded_variants == snapshot


def test_load_all_requirements() -> None:
    recipe_content = Path("tests/data/recipe_requirements.yaml").read_text()

    recipe_content = load_yaml(recipe_content)

    content = load_all_requirements(recipe_content)
    print(content)
    assert content["run"] == []
    assert content["run_exports"] == {
        "weak": ["weak-then", "weak-else", "weakreq"],
        "strong": ["strongreq"],
    }
    assert content["ignore_run_exports"] == {"from_package": ["python"]}


def test_load_recipe_with_missing_selectors(snapshot) -> None:
    osx_recipe = Path("tests/data/osx_recipe.yaml")

    namespace = {"osx": True, "unix": True}

    loaded_variants = parse_recipe_config_file(
        str(osx_recipe), namespace, allow_missing_selector=True
    )

    assert loaded_variants == snapshot


def test_load_all_tests(snapshot) -> None:
    recipe_content = Path("tests/data/recipe_tests.yaml").read_text()

    recipe_content = load_yaml(recipe_content)

    loaded_tests = load_all_tests(recipe_content)
    assert loaded_tests == snapshot

    # validate that tests section is a list of dictionaries
    # and also verify that dictionary preserver the right inner dict
    # let's find script test
    script_test = next(test for test in loaded_tests if "script" in test)
    # validate that it has run requirements as dictionary
    assert script_test["requirements"]["run"][0] == "pytest"

    # let's find python test
    python_test = next(test for test in loaded_tests if "python" in test)
    assert "mypkg" in python_test["python"]["imports"]
