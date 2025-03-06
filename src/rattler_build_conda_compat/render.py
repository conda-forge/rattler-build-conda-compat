# mypy: ignore-errors

from __future__ import annotations

from collections import OrderedDict
import json
from itertools import chain
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional

from conda_build.metadata import (
    MetaData as CondaMetaData,
    OPTIONALLY_ITERABLE_FIELDS,
)
from conda_build.config import get_or_merge_config
from conda_build.variants import (
    filter_combined_spec_to_used_keys,
    get_default_variant,
    validate_spec,
    combine_specs,
)
from conda_build.metadata import get_selectors, check_bad_chrs
from conda_build.config import Config

from rattler_build_conda_compat.jinja.jinja import render_recipe_with_context
from rattler_build_conda_compat.loader import load_yaml, parse_recipe_config_file
from rattler_build_conda_compat.utils import _get_recipe_metadata, find_recipe
from rattler_build_conda_compat.yaml import _yaml_object


class MetaData(CondaMetaData):
    def __init__(
        self,
        path,
        rendered_recipe: Optional[dict] = None,
        config=None,
        variant=None,
    ):
        self.config: Config = get_or_merge_config(config, variant=variant)
        if os.path.isfile(path):
            self._meta_path = path
            self._meta_name = os.path.basename(path)
            self.path = os.path.dirname(path)
        else:
            self._meta_name = "recipe.yaml"
            self._meta_path = find_recipe(path)
            self.path = os.path.dirname(self._meta_path)

        self._rendered = False

        if not rendered_recipe:
            self.meta = self.parse_recipe()
            self.meta["about"] = self.meta.get("about", {})
            self.meta["extra"] = self.meta.get("extra", {})
        else:
            self.meta = rendered_recipe
            self._rendered = True
            self.meta["about"] = self.meta["recipe"].get("about", {})
            self.meta["extra"] = self.meta["recipe"].get("extra", {})

        self.final = True
        self.undefined_jinja_vars = []

        self.requirements_path = os.path.join(self.path, "requirements.txt")

    def parse_recipe(self) -> dict[str, Any]:
        recipe_path: Path = Path(self.path) / self._meta_name

        yaml_content = load_yaml(recipe_path.read_text(encoding="utf-8"))

        return render_recipe_with_context(yaml_content)

    def name(self) -> str:
        """
        Overrides the conda_build.metadata.MetaData.name method.
        Returns the name of the package.
        If recipe has multiple outputs, it will return the name of the `recipe` field.
        Otherwise it will return the name of the `package` field.

        Raises:
            - CondaBuildUserError: If the `name` contains bad characters.
            - ValueError: If the name is not lowercase or missing.

        """
        name = _get_recipe_metadata(self.meta, "name", rendered=self._rendered)

        if not name:
            raise ValueError(f"Error: package/name missing in: {self.meta_path!r}")

        if name != name.lower():
            raise ValueError(f"Error: package/name must be lowercase, got: {name!r}")

        check_bad_chrs(name, "package/name")
        return name

    def version(self) -> str:
        """
        Overrides the conda_build.metadata.MetaData.version method.
        Returns the version of the package.
        If recipe has multiple outputs, it will return the version of the `recipe` field.
        Otherwise it will return the version of the `package` field.

        Raises:
            - CondaBuildUserError: If the `version` contains bad characters.
            - ValueError: If the version starts with a period or version is missing.
        """
        version = _get_recipe_metadata(self.meta, "version", rendered=self._rendered)

        if not version:
            raise ValueError(f"Error: package/version missing in: {self.meta_path!r}")

        check_bad_chrs(version, "package/version")
        if version.startswith("."):
            raise ValueError(f"Fully-rendered version can't start with period -  got {version!r}")
        return version

    def render_recipes(self, variants) -> List[Dict]:
        build_platform_and_arch = f"{self.config.platform}-{self.config.arch}"
        target_platform_and_arch = f"{self.config.host_platform}-{self.config.host_arch}"

        yaml = _yaml_object()
        try:
            with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as outfile:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as variants_file:
                    # dump variants in our variants that will be used to generate recipe
                    if variants:
                        yaml.dump(variants, variants_file)

                    variants_path = variants_file.name

                    run_args = [
                        "rattler-build",
                        "build",
                        "--render-only",
                        "--recipe",
                        self.path,
                        "--target-platform",
                        target_platform_and_arch,
                        "--build-platform",
                        build_platform_and_arch,
                    ]

                    if variants:
                        run_args.extend(["-m", variants_path])
                    subprocess.run(run_args, check=True, stdout=outfile, env=os.environ)

                    outfile.seek(0)
                    content = outfile.read()
                    metadata = json.loads(content)
            return metadata if isinstance(metadata, list) else [metadata]

        except Exception as e:
            raise e

    def get_used_vars(self, force_top_level=False, force_global=False):
        if "build_configuration" not in self.meta:
            # it could be that we skip build for this platform
            # so no variants have been discovered
            # return empty
            return set()

        used_vars = [
            var.replace("-", "_") for var in self.meta["build_configuration"]["variant"].keys()
        ]

        # in conda-build target-platform is not returned as part of yaml vars
        # so it's included manually
        # in our case it is always present in build_configuration.variant
        # so we remove it when it's noarch
        if "target_platform" in self.config.variant and self.noarch:
            used_vars.remove("target_platform")

        return set(used_vars)

    def get_used_variant(self) -> Dict:
        if "build_configuration" not in self.meta:
            # it could be that we skip build for this platform
            # so no variants have been discovered
            # return empty
            return {}

        used_variant = dict(self.meta["build_configuration"]["variant"])

        used_variant_key_normalized = {}

        for key, value in used_variant.items():
            normalized_key = key.replace("-", "_")
            used_variant_key_normalized[normalized_key] = value

        # in conda-build target-platform is not returned as part of yaml vars
        # so it's included manually
        # in our case it is always present in build_configuration.variant
        # so we remove it when it's noarch
        if "target_platform" in used_variant_key_normalized and self.noarch:
            used_variant_key_normalized.pop("target_platform")

        return used_variant_key_normalized

    def get_used_loop_vars(self, force_top_level=False, force_global=False):
        return {
            var
            for var in self.get_used_vars(
                force_top_level=force_top_level, force_global=force_global
            )
            if var in self.get_loop_vars()
        }

    def get_section(self, name):
        if not self._rendered:
            section = self.meta.get(name)
        else:
            section = self.meta.get("recipe", {}).get(name)

        if name in OPTIONALLY_ITERABLE_FIELDS:
            if not section:
                return []
            elif isinstance(section, dict):
                return [section]
            elif not isinstance(section, list):
                raise ValueError(f"Expected {name} to be a list")
        else:
            if not section:
                return {}
            elif not isinstance(section, dict):
                raise ValueError(f"Expected {name} to be a dict")

        return section


def render_recipe(
    recipe_path,
    config=None,
    variants=None,
) -> List[MetaData]:
    """Returns a list of tuples, each consisting of

    (metadata-object, needs_download, needs_render_in_env)

    You get one tuple per variant.  Outputs are not factored in here (subpackages won't affect these
    results returned here.)
    """

    metadata = MetaData(recipe_path, config=config)
    recipes = metadata.render_recipes(variants)

    metadatas: list[MetaData] = []
    if not recipes:
        return [metadata]

    for recipe in recipes:
        metadata = MetaData(recipe_path, rendered_recipe=recipe, config=config)
        # just to have the same interface as conda_build
        metadatas.append(metadata)

    return metadatas


def render(
    recipe_path: os.PathLike,
    config: Optional[Config] = None,
    variants: Optional[Dict[str, Any] | None] = None,
    **kwargs,
):
    """Given path to a recipe, return the MetaData object(s) representing that recipe, with jinja2
       templates evaluated.

    Returns a list of (metadata, needs_download, needs_reparse in env) tuples
    """

    config = get_or_merge_config(config, **kwargs)

    arg = recipe_path
    if os.path.isfile(arg):
        if arg.endswith(".yaml"):
            recipe_dir = os.path.dirname(arg)
        else:
            raise ValueError("Recipe don't have a valid extension: %s" % arg)
    else:
        recipe_dir = os.path.abspath(arg)

    metadata_tuples = render_recipe(
        recipe_dir,
        config=config,
        variants=variants,
    )

    for m in metadata_tuples:
        if not hasattr(m.config, "variants") or not m.config.variant:
            m.config.ignore_system_variants = True

            if os.path.isfile(os.path.join(m.path, "variants.yaml")):
                m.config.variant_config_files = [os.path.join(m.path, "variants.yaml")]

            used_variant = m.get_used_variant()

            package_variants = rattler_get_package_variants(m, variants=variants)

            m.config.variants = package_variants[:]

            # we need to discard variants that we don't use
            for pkg_variant in package_variants[:]:
                for (
                    used_variant_key,
                    used_variant_value,
                ) in used_variant.items():
                    if used_variant_key in pkg_variant:
                        if (
                            pkg_variant[used_variant_key] != used_variant_value
                            and pkg_variant in package_variants
                        ):
                            package_variants.remove(pkg_variant)

            m.config.variant = package_variants[0]

            # These are always the full set.  just 'variants' is the one that gets
            #     used mostly, and can be reduced
            m.config.input_variants = m.config.variants
            m.config.variants = package_variants

    return [(m, False, False) for m in metadata_tuples]


def get_package_combined_spec(recipedir_or_metadata, config, variants=None):
    # this function is *vendored* version of
    # get_package_combined_spec from conda_build
    # with few changes to support rattler-build

    config = recipedir_or_metadata.config
    namespace = get_selectors(config)
    variants_paths = config.variant_config_files

    specs = OrderedDict(internal_defaults=get_default_variant(config))

    for variant_path in variants_paths:
        specs[variant_path] = parse_recipe_config_file(variant_path, namespace)

    # this is the override of the variants from files and args with values from CLI or env vars
    if hasattr(config, "variant") and config.variant:
        specs["config.variant"] = config.variant
    if variants:
        specs["argument_variants"] = variants

    for f, spec in specs.items():
        validate_spec(f, spec)

    # this merges each of the specs, providing a debug message when a given setting is overridden
    #      by a later spec
    combined_spec = combine_specs(specs, log_output=config.verbose)

    return combined_spec, specs


def _reduce_variants(m: MetaData, variants: list[dict] | None) -> tuple[dict, dict]:
    """Reduce variants dict to the used subset

    Avoids combinatorial explosion in rattler_get_package_variants
    for unused variants
    """
    if not variants:
        return {}, {}
    all_variants = variants
    # track the used variables
    all_used_vars = set()
    all_used_vars.update(m.get_used_vars())
    # keep zip_keys and everything zipped
    # since the zipping happens, even on unused keys
    all_used_vars.add("zip_keys")
    all_zip_keys = set(chain(*variants.get("zip_keys", [])))
    all_used_vars.update(all_zip_keys)

    # compute reduced variant dict,
    # only containing used keys
    reduced_variants = {key: all_variants[key] for key in all_variants if key in all_used_vars}
    if not reduced_variants:
        # nothing used, return original
        return variants, {}

    # keep track of unused variants to put back
    # after exploding the list
    unused_variants = {}
    for key in all_variants:
        if key not in reduced_variants:
            unused_variants[key] = all_variants[key]
    return reduced_variants, unused_variants


def rattler_get_package_variants(recipedir_or_metadata, config=None, variants=None):
    # this function is *vendored* version of
    # get_package_variants from conda_build
    # with few changes to support rattler-build

    # reduce variants to used fields before exploding the matrix
    # avoids computing potentially thousands of unused variants
    # in e.g. conda-smithy rerender
    reduced_variants, unused_variants = _reduce_variants(recipedir_or_metadata, variants)
    combined_spec, specs = get_package_combined_spec(
        recipedir_or_metadata, config=config, variants=reduced_variants
    )
    package_variants = filter_combined_spec_to_used_keys(combined_spec, specs=specs)
    # restore unused fields after exploding the list
    for pkg_variant in package_variants:
        pkg_variant.update(unused_variants)
    return package_variants
