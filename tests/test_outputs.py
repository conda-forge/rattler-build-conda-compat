from __future__ import annotations

from pathlib import Path

from rattler_build_conda_compat.outputs import (
    flatten_staging_inheritance,
    get_output_name,
    is_staging_output,
    iter_package_outputs,
)
from rattler_build_conda_compat.yaml import _dump_yaml_to_string, _yaml_object

DATA = Path(__file__).parent / "data"


def _load_flattened(fixture: str) -> dict:
    text = (DATA / fixture).read_text()
    return _yaml_object().load(flatten_staging_inheritance(text))


def test_is_staging_output_true_for_staging() -> None:
    assert is_staging_output({"staging": {"name": "libfoo-build"}}) is True


def test_is_staging_output_false_for_package() -> None:
    assert is_staging_output({"package": {"name": "libfoo"}}) is False


def test_is_staging_output_false_for_mixed() -> None:
    # If both keys are present (malformed), treat it as a package output so
    # downstream logic errs on the side of publishing.
    output = {"staging": {"name": "x"}, "package": {"name": "x"}}
    assert is_staging_output(output) is False


def test_iter_package_outputs_filters_staging() -> None:
    outputs = [
        {"staging": {"name": "libfoo-build"}},
        {"package": {"name": "libfoo"}},
        {"staging": {"name": "libbar-build"}},
        {"package": {"name": "libbar"}},
    ]
    names = [get_output_name(o) for o in iter_package_outputs(outputs)]
    assert names == ["libfoo", "libbar"]


def test_get_output_name_package() -> None:
    assert get_output_name({"package": {"name": "libfoo"}}) == "libfoo"


def test_get_output_name_staging() -> None:
    assert get_output_name({"staging": {"name": "libfoo-build"}}) == "libfoo-build"


def test_get_output_name_missing() -> None:
    assert get_output_name({"build": {"number": 0}}) is None


def test_flatten_staging_inheritance_string_inherit() -> None:
    flattened = _load_flattened("staging_outputs.yaml")

    assert [get_output_name(o) for o in flattened["outputs"]] == ["libfoo"]
    libfoo = flattened["outputs"][0]
    assert "inherit" not in libfoo
    assert list(libfoo["requirements"]["build"]) == ["${{ compiler('c') }}"]
    assert list(libfoo["requirements"]["run"]) == ["python"]
    # staging source was promoted to the inheriting output
    assert libfoo["source"][0]["url"] == "https://example.com/libfoo-${{ version }}.tar.gz"


def test_flatten_staging_inheritance_no_anchors() -> None:
    flattened = _load_flattened("staging_outputs_gdal.yaml")
    new_yaml = _dump_yaml_to_string(flattened)
    assert "id0" not in new_yaml


def test_flatten_staging_inheritance_merges_host_and_dedups() -> None:
    flattened = _load_flattened("staging_outputs_libtorch.yaml")

    assert [get_output_name(o) for o in flattened["outputs"]] == ["libtorch", "pytorch"]

    libtorch_reqs = flattened["outputs"][0]["requirements"]
    assert list(libtorch_reqs["build"]) == ["cxx_compiler_stub"]
    # staging deps come first, then pre-existing, python is not duplicated
    assert list(libtorch_reqs["host"]) == ["cudnn 9.*", "mkl-devel", "python"]
    assert list(libtorch_reqs["run"]) == ["cudnn 9.*"]
    assert "inherit" not in flattened["outputs"][0]

    pytorch_reqs = flattened["outputs"][1]["requirements"]
    assert list(pytorch_reqs["build"]) == ["cxx_compiler_stub"]
    assert list(pytorch_reqs["host"]) == ["cudnn 9.*", "mkl-devel", "python"]
    assert list(pytorch_reqs["run"]) == ["libtorch", "python"]
    assert "inherit" not in flattened["outputs"][1]


def test_flatten_staging_inheritance_no_staging_is_noop() -> None:
    text = "package:\n  name: libfoo\nrequirements:\n  host:\n    - python\n"
    # no "staging" substring, helper returns the exact same object
    assert flatten_staging_inheritance(text) is text


def test_flatten_staging_inheritance_returns_input_when_only_substring() -> None:
    # "staging" appears in a description but there are no staging outputs,
    # so the helper should still return the original text unchanged.
    text = """\
package:
  name: libfoo
about:
  summary: "pre-staging build helper"
"""
    assert flatten_staging_inheritance(text) == text
