from rattler_build_conda_compat import yaml
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
