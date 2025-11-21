from rattler_build_conda_compat.conditional_list import visit_conditional_list


def test_visit_conditional_list() -> None:
    # Plain lists or objects
    assert list(visit_conditional_list([1, 2, 3])) == [1, 2, 3]
    assert list(visit_conditional_list(1)) == [1]

    # With an if statement
    assert list(visit_conditional_list({"if": True, "then": 1, "else": 2})) == [1, 2]
    assert list(
        visit_conditional_list(
            {
                "if": True,
                "then": [1, 2],
            }
        )
    ) == [1, 2]
    assert list(visit_conditional_list({"if": True, "then": [1, 2], "else": 3})) == [
        1,
        2,
        3,
    ]
    assert list(visit_conditional_list({"if": True, "then": [1, 2], "else": [3, 4]})) == [
        1,
        2,
        3,
        4,
    ]

    # Multiple if statements
    assert list(
        visit_conditional_list(
            [{"if": True, "then": [1, 2], "else": 3}, {"if": False, "then": [4]}]
        )
    ) == [1, 2, 3, 4]

    # With an evaluator
    assert list(
        visit_conditional_list(
            [{"if": False, "then": [1, 2], "else": 3}, {"if": True, "then": [4]}],
            evaluator=lambda x: x,
        )
    ) == [3, 4]


def test_visit_conditional_list_nested_if() -> None:
    assert list(
        visit_conditional_list(
            [
                {"if": True, "then": {"if": True, "then": 1, "else": 2}, "else": 3},
                {"if": False, "then": [4]},
            ]
        )
    ) == [1, 2, 3, 4]
