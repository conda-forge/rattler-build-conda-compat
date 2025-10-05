from __future__ import annotations

import copy
import hashlib
import logging
import re
from typing import TYPE_CHECKING, Any, Literal

import requests

from rattler_build_conda_compat.jinja.jinja import jinja_env, load_recipe_context
from rattler_build_conda_compat.recipe_sources import get_all_sources
from rattler_build_conda_compat.yaml import _dump_yaml_to_string, _yaml_object

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from pathlib import Path

logger = logging.getLogger(__name__)

HashType = Literal["md5", "sha256"]


def _update_build_number_in_context(recipe: dict[str, Any], new_build_number: int) -> bool:
    for key in recipe.get("context", {}):
        if key.startswith("build_") or key == "build":
            recipe["context"][key] = new_build_number
            return True
    return False


def _update_build_number_in_recipe(recipe: dict[str, Any], new_build_number: int) -> bool:
    is_modified = False
    if "build" in recipe and "number" in recipe["build"]:
        recipe["build"]["number"] = new_build_number
        is_modified = True

    if "outputs" in recipe:
        for output in recipe["outputs"]:
            if "build" in output and "number" in output["build"]:
                output["build"]["number"] = new_build_number
                is_modified = True

    return is_modified


def update_build_number(file: Path, new_build_number: int = 0) -> str:
    """
    Update the build number in the recipe file.

    Arguments:
    ----------
    * `file` - The path to the recipe file.
    * `new_build_number` - The new build number to use. (default: 0)

    Returns:
    --------
    The updated recipe as a string.
    """
    yaml = _yaml_object()
    with file.open("r") as f:
        data = yaml.load(f)
    build_number_modified = _update_build_number_in_context(data, new_build_number)
    if not build_number_modified:
        _update_build_number_in_recipe(data, new_build_number)

    return _dump_yaml_to_string(data)


class CouldNotUpdateVersionError(Exception):
    NO_CONTEXT = "Could not find context in recipe"
    NO_VERSION = "Could not find version in recipe context"

    def __init__(self, message: str = "Could not update version") -> None:
        self.message = message
        super().__init__(self.message)


class Hash:
    def __init__(self, hash_type: HashType, hash_value: str) -> None:
        self.hash_type = hash_type
        self.hash_value = hash_value

    def __str__(self) -> str:
        return f"{self.hash_type}: {self.hash_value}"


def _has_jinja_version(url: str) -> bool:
    """Check if the URL has a jinja `${{ version }}` in it."""
    pattern = r"\${{\s*version"
    return re.search(pattern, url) is not None


def update_hash(source: MutableMapping[str, Any], url: str, hash_: Hash | None) -> None:
    """
    Update the sha256 hash in the source dictionary.

    Arguments:
    ----------
    * `source` - The source dictionary to update.
    * `url` - The URL to download and hash (if no hash is provided).
    * `hash_` - The hash to use. If not provided, the file will be downloaded and `sha256` hashed.
    """
    hash_type: HashType = hash_.hash_type if hash_ is not None else "sha256"
    # delete all old hashes that we are not updating
    all_hash_types: set[HashType] = {"md5", "sha256"}
    for key in all_hash_types - {hash_type}:
        if key in source:
            del source[key]

    if hash_ is not None:
        source[hash_.hash_type] = hash_.hash_value
    else:
        # download and hash the file
        hasher = hashlib.sha256()
        print(f"Retrieving and hashing {url}")
        with requests.get(url, stream=True, timeout=100) as r:
            for chunk in r.iter_content(chunk_size=4096):
                hasher.update(chunk)
        source["sha256"] = hasher.hexdigest()


def update_version(file: Path, new_version: str, hash_: Hash | None) -> str:
    """
    Update the version in the recipe file.

    Arguments:
    ----------
    * `file` - The path to the recipe file.
    * `new_version` - The new version to use.
    * `hash_type` - The hash type to use. If not provided, the file will be downloaded and `sha256` hashed.

    Returns:
    --------
    The updated recipe as a string.
    """

    yaml = _yaml_object()
    with file.open("r") as f:
        data = yaml.load(f)

    if "context" not in data:
        raise CouldNotUpdateVersionError(CouldNotUpdateVersionError.NO_CONTEXT)
    if "version" not in data["context"]:
        raise CouldNotUpdateVersionError(CouldNotUpdateVersionError.NO_VERSION)

    data["context"]["version"] = new_version

    # set up the jinja context
    env = jinja_env()
    context = copy.deepcopy(data.get("context", {}))
    context_variables = load_recipe_context(context, env)
    # for r-recipes we add the default `cran_mirror` variable
    context_variables["cran_mirror"] = "https://cran.r-project.org"

    for source in get_all_sources(data):
        # render the whole URL and find the hash
        if "url" not in source:
            continue

        url = source["url"]
        if isinstance(url, list):
            url = url[0]

        if not _has_jinja_version(url):
            continue

        template = env.from_string(url)
        rendered_url = template.render(context_variables)

        update_hash(source, rendered_url, hash_)

    return _dump_yaml_to_string(data)
