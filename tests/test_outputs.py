from __future__ import annotations

from rattler_build_conda_compat.outputs import (
    get_output_name,
    is_staging_output,
    iter_package_outputs,
)


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
