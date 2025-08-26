from __future__ import annotations

import io
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.representer import SafeRepresenter, ScalarNode


# Custom constructor for loading floats as strings
def float_as_string_constructor(loader, node) -> str:  # noqa: ANN001
    return loader.construct_scalar(node)


# _yaml_represent_str adapted from conda-smithy @ a52dcf7ab09ef9007702c5a89dc18f0735295036
# Copyright 2025 conda-forge contributors
# License: BSD-3-Clause  # noqa: ERA001
def _yaml_represent_str(yaml_representer: SafeRepresenter, data: str) -> ScalarNode:
    # boolean types in cbc and other sources get converted to strings by conda-build
    # let's go back to booleans
    if data in {"true", "false"}:
        return SafeRepresenter.represent_bool(yaml_representer, data == "true")
    return yaml_representer.represent_str(data)


def _yaml_object() -> YAML:
    yaml = YAML(typ="rt")
    yaml.Constructor.add_constructor("tag:yaml.org,2002:float", float_as_string_constructor)
    yaml.representer.add_representer(str, _yaml_represent_str)
    yaml.allow_duplicate_keys = False
    yaml.preserve_quotes = True
    yaml.width = 320
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _dump_yaml_to_string(data: Any) -> str:  # noqa: ANN401
    yaml = _yaml_object()
    with io.StringIO() as f:
        yaml.dump(data, f)
        return f.getvalue()
