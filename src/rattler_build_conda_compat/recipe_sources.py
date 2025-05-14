from __future__ import annotations

import typing
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any, List, Union, cast

from rattler_build_conda_compat.jinja.jinja import (
    RecipeWithContext,
    jinja_env,
    load_recipe_context,
)
from rattler_build_conda_compat.loader import _eval_selector
from rattler_build_conda_compat.variant_config import variant_combinations

from .conditional_list import ConditionalList, visit_conditional_list

if typing.TYPE_CHECKING:
    from collections.abc import Iterator


OptionalUrlList = Union[str, List[str], None]


@dataclass(frozen=True)
class Source:
    url: str | list[str]
    template: str | list[str]
    context: dict[str, str] | None = None
    sha256: str | None = None
    md5: str | None = None

    def __getitem__(self, key: str) -> str | list[str] | None:
        return self.__dict__[key]

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
    sources = typing.cast(ConditionalList[MutableMapping[str, Any]], sources)

    # Try getting all url top-level sources
    if sources is not None:
        source_list = visit_conditional_list(sources, None)
        for source in source_list:
            yield source

    cache_output = recipe.get("cache", None)
    if cache_output is not None:
        sources = cache_output.get("source", None)
        sources = typing.cast(ConditionalList[MutableMapping[str, Any]], sources)
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
        sources = typing.cast(ConditionalList[MutableMapping[str, Any]], sources)
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
        if isinstance(source["url"], list):
            return source["url"][0]
        return source["url"]

    return (get_first_url(source) for source in get_all_sources(recipe) if "url" in source)


def render_all_sources(  # noqa: C901
    recipe: RecipeWithContext,
    variants: list[dict[str, list[str]]],
    override_version: str | None = None,
) -> set[Source]:
    """
    This function should render _all_ URL sources from the given recipe and with the given variants.
    Variants can be loaded with the `variant_config.variant_combinations` module.
    Optionally, you can override the version in the recipe context to render URLs with a different version.
    """

    def render(template: str | list[str], context: dict[str, str]) -> str | list[str]:
        if isinstance(template, list):
            return [cast(str, render(t, context)) for t in template]
        template = env.from_string(template)
        return template.render(context)

    if override_version is not None:
        recipe["context"]["version"] = override_version

    final_sources = set()
    for v in variants:
        combinations = variant_combinations(v)
        for combination in combinations:
            env = jinja_env(combination)

            context = recipe.get("context", {})
            # render out the context section and retrieve dictionary
            context_variables = load_recipe_context(context, env)

            # now evaluate the if / else statements
            sources = recipe.get("source")
            if sources:
                if not isinstance(sources, list):
                    sources = [sources]

                for elem in visit_conditional_list(
                    sources,
                    lambda x, combination=env.globals: _eval_selector(x, combination),  # type: ignore[misc]
                ):
                    # we need to explicitly cast here
                    elem_dict = typing.cast(dict[str, Any], elem)
                    sha256, md5 = None, None
                    if elem_dict.get("sha256") is not None:
                        sha256 = typing.cast(
                            str, render(str(elem_dict["sha256"]), context_variables)
                        )
                    if elem_dict.get("md5") is not None:
                        md5 = typing.cast(str, render(str(elem_dict["md5"]), context_variables))
                    if "url" in elem_dict:
                        as_url = Source(
                            url=render(elem_dict["url"], context_variables),
                            template=elem_dict["url"],
                            sha256=sha256,
                            md5=md5,
                            context=context_variables,
                        )
                        final_sources.add(as_url)

    return final_sources
