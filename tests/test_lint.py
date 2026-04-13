from __future__ import annotations

from rattler_build_conda_compat.lint import lint_recipe_tests


def test_lint_recipe_tests_skips_staging_outputs() -> None:
    """Staging outputs produce no artifact and must not be flagged for missing tests.

    On trunk (without the staging fix), the staging entry has no `tests:` key,
    so `lint_recipe_tests` appends a "'???' output doesn't have any tests" hint
    for it. With the fix, staging outputs are skipped entirely and that hint
    disappears — the only remaining hint (if any) is for real package outputs.
    """
    outputs = [
        {"staging": {"name": "libfoo-build"}},
        {
            "name": "libfoo",
            "tests": {"script": ["test -f $PREFIX/lib/libfoo.so"]},
        },
    ]
    lints, hints = lint_recipe_tests(test_section={}, outputs_section=outputs)
    assert lints == []
    # Key assertion: no hint at all, because every *package* output has tests
    # and the staging output is not considered.
    assert hints == []


def test_lint_recipe_tests_still_flags_missing_tests_on_package_outputs() -> None:
    """Regression: non-staging outputs without tests must still produce a hint.

    On trunk: two hints (one for staging's '???', one for 'libfoo').
    With fix: one hint (only 'libfoo').
    """
    outputs = [
        {"staging": {"name": "libfoo-build"}},
        {"name": "libfoo"},  # no tests
        {
            "name": "libfoo-dev",
            "tests": {"script": ["true"]},
        },
    ]
    _lints, hints = lint_recipe_tests(test_section={}, outputs_section=outputs)
    assert len(hints) == 1
    assert "'libfoo'" in hints[0]
