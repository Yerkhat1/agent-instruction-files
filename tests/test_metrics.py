"""Metrics are the measurement instrument, so they are tested against known code."""

import pytest

from policyprop.metrics import (
    DEFAULT_LINE_LIMIT,
    docstring_coverage,
    line_length_compliance,
    type_hint_coverage,
)

ANNOTATED = """
def a(x: int) -> int:
    return x

def b(y) -> None:
    pass

def c(z):
    return z

class K:
    def m(self):
        return 1

    def n(self, q: str):
        return q
"""


def test_type_hints_counts_return_or_param_annotations():
    # a: both, b: return, n: param -> 3 of 5; self is ignored so m is unannotated.
    assert type_hint_coverage(ANNOTATED) == (3, 5)


def test_type_hints_ignores_self_and_cls():
    src = "class K:\n    def m(self):\n        pass\n"
    assert type_hint_coverage(src) == (0, 1)


def test_type_hints_counts_async_functions():
    assert type_hint_coverage("async def f() -> None:\n    pass\n") == (1, 1)


def test_docstrings_skip_private_names():
    src = '''
def public():
    """Doc."""

def _private():
    pass

class Shown:
    """Doc."""

class _Hidden:
    pass
'''
    assert docstring_coverage(src) == (2, 2)


def test_docstrings_counts_undocumented():
    assert docstring_coverage("def f():\n    pass\n") == (0, 1)


def test_line_length_counts_lines_within_limit():
    src = "x = 1\n" + "y = '" + "a" * 200 + "'\n"
    assert line_length_compliance(src) == (1, 2)


def test_line_length_respects_custom_limit():
    assert line_length_compliance("abcdef\n", limit=3) == (0, 1)
    assert line_length_compliance("abc\n", limit=3) == (1, 1)


def test_line_length_rejects_nonpositive_limit():
    with pytest.raises(ValueError, match="must be positive"):
        line_length_compliance("x = 1\n", limit=0)


def test_default_limit_is_the_formatter_default():
    assert DEFAULT_LINE_LIMIT == 88


@pytest.mark.parametrize("metric", [type_hint_coverage, docstring_coverage])
def test_unparseable_source_returns_none(metric):
    # Years of real repositories contain files that do not parse. They are skipped.
    assert metric("def broken(:\n") is None


def test_empty_file_has_no_lines_to_judge():
    assert line_length_compliance("") is None
