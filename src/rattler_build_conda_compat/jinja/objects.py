from __future__ import annotations

from typing import Any


def _stub_compatible_pin(*args: Any, **kwargs: Any) -> str:  # noqa: ARG001, ANN401
    return f"compatible_pin {args[0]}"


def _stub_subpackage_pin(*args: Any, **kwargs: Any) -> str:  # noqa: ARG001, ANN401
    return f"subpackage_pin {args[0]}"


def _stub_match(*args: Any, **kwargs: Any) -> str:  # noqa: ARG001, ANN401
    return f"match {args[0]}"
