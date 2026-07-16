from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import Any, cast

from rattler_build_conda_compat.jinja.jinja import (
    RecipeWithContext,
    render_recipe_with_context,
)
from rattler_build_conda_compat.loader import _eval_selector
from rattler_build_conda_compat.variant_config import variant_combinations

from .conditional_list import ConditionalList, visit_conditional_list

if typing.TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, MutableMapping


OptionalUrlList = str | list[str] | None


@dataclass(frozen=True)
class Source:
    url: str | list[str]
    template: str | list[str]
    context: dict[str, str] | None = None
    sha256: str | None = None
    md5: str | None = None

    def __getitem__(self, key: str) -> str | list[str] | None:
        return cast("str | list[str] | None", self.__dict__[key])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Source):
            return NotImplemented
        return (self.url, self.sha256, self.md5) == (other.url, other.sha256, other.md5)

    def __hash__(self) -> int:
        return hash((tuple(self.url), self.sha256, self.md5))


def get_all_sources(recipe: MutableMapping[str, Any]) -> Iterator[MutableMapping[str, Any]]:
    """
    Get all sources from the recipe. This can be from a list of sources,
    a single source, or conditional and its branches.

    Arguments
    ---------
    * `recipe` - The recipe to inspect. This should be a yaml object.

    Returns
    -------
    A list of source objects.
    """
    sources = recipe.get("source", None)
    sources = typing.cast("ConditionalList[MutableMapping[str, Any]]", sources)

    # Try getting all url top-level sources
    if sources is not None:
        source_list = visit_conditional_list(sources, None)
        for source in source_list:
            yield source

    outputs = recipe.get("outputs", None)
    if outputs is None:
        return

    outputs = visit_conditional_list(outputs, None)
    for output in outputs:
        sources = output.get("source", None)
        sources = typing.cast("ConditionalList[MutableMapping[str, Any]]", sources)
        if sources is None:
            continue
        source_list = visit_conditional_list(sources, None)
        for source in source_list:
            yield source


def get_all_url_sources(recipe: MutableMapping[str, Any]) -> Iterator[str]:
    """
    Get all url sources from the recipe. This can be from a list of sources,
    a single source, or conditional and its branches.

    Arguments
    ---------
    * `recipe` - The recipe to inspect. This should be a yaml object.

    Returns
    -------
    A list of URLs.
    """

    def get_first_url(source: MutableMapping[str, Any]) -> str:
        url = source["url"]
        if isinstance(url, list):
            return str(url[0])
        return str(url)

    return (get_first_url(source) for source in get_all_sources(recipe) if "url" in source)


def _collect_source_sections(
    recipe: Mapping[str, Any],
    selector: typing.Callable[[str], bool],
) -> list[Any]:
    """Collect raw source sections from top-level, cache, and outputs."""
    sections: list[Any] = []

    top_level = recipe.get("source")
    if top_level:
        sections.append(top_level)

    cache = recipe.get("cache")
    if cache is not None:
        cache = typing.cast("dict[str, Any]", cache)
        cache_sources = cache.get("source")
        if cache_sources:
            sections.append(cache_sources)

    outputs = recipe.get("outputs")
    if outputs:
        for output in visit_conditional_list(outputs, selector):
            output_dict = typing.cast("dict[str, Any]", output)
            output_sources = output_dict.get("source")
            if output_sources:
                sections.append(output_sources)

    return sections


def _selector_namespace(variant_config: Mapping[str, Any]) -> dict[str, Any]:
    """
    Build the namespace used to evaluate `if:` selector expressions: platform
    shortcuts (`linux`, `x86_64`, `unix`, ...) derived from the target platform
    plus the variant variables themselves.
    """
    namespace: dict[str, Any] = {
        "is_unix": lambda x: not x.startswith("win"),
        "is_win": lambda x: x.startswith("win"),
        "is_linux": lambda x: x.startswith("linux"),
    }

    target_platform = str(variant_config.get("target_platform", "linux-64"))
    if target_platform != "noarch":
        platform, arch = target_platform.split("-")
        namespace[platform] = True
        if arch == "64":
            namespace["x86_64"] = True
        elif arch == "32":
            namespace["x86"] = True
        else:
            namespace[arch] = True

    namespace["unix"] = not target_platform.startswith("win")
    namespace.update(variant_config)
    return namespace


def _iter_source_dicts(
    recipe: Mapping[str, Any],
    selector: typing.Callable[[str], bool],
) -> Iterator[dict[str, Any]]:
    """Iterate over the source dictionaries selected by `selector`."""
    for sources in _collect_source_sections(recipe, selector):
        source_list = sources if isinstance(sources, list) else [sources]
        for elem in visit_conditional_list(source_list, selector):
            yield typing.cast("dict[str, Any]", elem)


def render_all_sources(
    recipe: RecipeWithContext,
    variants: list[dict[str, list[str]]],
    override_version: str | None = None,
) -> set[Source]:
    """
    This function should render _all_ URL sources from the given recipe and with the given variants.
    Variants can be loaded with the `variant_config.variant_combinations` module.
    Optionally, you can override the version in the recipe context to render URLs with a different version.
    """
    if override_version is not None:
        recipe["context"]["version"] = override_version

    final_sources = set()
    for v in variants:
        combinations = variant_combinations(v)
        for combination in combinations:
            # substitute the context and variant variables into the whole recipe
            rendered = render_recipe_with_context(recipe, combination)
            context_variables = typing.cast("dict[str, str]", rendered.get("context", {}))

            # now evaluate the if / else statements
            namespace = _selector_namespace(combination)
            selector = lambda x, namespace=namespace: _eval_selector(x, namespace)  # noqa: E731

            # the rendered recipe preserves the raw recipe's structure, so the
            # source dictionaries of both trees pair up
            for raw_elem, elem in zip(
                _iter_source_dicts(recipe, selector),
                _iter_source_dicts(rendered, selector),
                strict=True,
            ):
                sha256, md5 = None, None
                if elem.get("sha256") is not None:
                    sha256 = str(elem["sha256"])
                if elem.get("md5") is not None:
                    md5 = str(elem["md5"])
                if "url" in elem:
                    as_url = Source(
                        url=elem["url"],
                        template=raw_elem["url"],
                        sha256=sha256,
                        md5=md5,
                        context=context_variables,
                    )
                    final_sources.add(as_url)

    return final_sources
