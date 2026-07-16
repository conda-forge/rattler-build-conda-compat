from __future__ import annotations

from typing import Any


class _UnresolvedArgumentError(ValueError):
    """Raised when a stub helper receives an argument that did not resolve.

    ``render_context`` treats a raising helper as "keep the expression
    verbatim", so e.g. ``${{ pin_subpackage(name_var) }}`` with an undefined
    ``name_var`` survives as-is instead of rendering to ``subpackage_pin
    None``. conda-smithy's linter skips requirement entries containing
    ``{{``, so the verbatim form stays invisible to it, just like the old
    jinja2-based renderer's output did.
    """


def _first_resolved_arg(*args: Any) -> Any:  # noqa: ANN401
    if not args or args[0] is None:
        raise _UnresolvedArgumentError
    return args[0]


def _stub_compatible_pin(*args: Any, **kwargs: Any) -> str:  # noqa: ARG001, ANN401
    return f"compatible_pin {_first_resolved_arg(*args)}"


def _stub_subpackage_pin(*args: Any, **kwargs: Any) -> str:  # noqa: ARG001, ANN401
    return f"subpackage_pin {_first_resolved_arg(*args)}"


def _stub_match(*args: Any, **kwargs: Any) -> str:  # noqa: ARG001, ANN401
    return f"match {_first_resolved_arg(*args)}"
