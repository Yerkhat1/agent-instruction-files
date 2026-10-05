"""Static compliance metrics.

Each metric reads Python source and returns (satisfying, total). No language model
is involved at any point: every number traces to an AST walk or a line scan.
"""

from __future__ import annotations

import ast
from typing import Final

#: Default maximum line length. 88 is the Black/Ruff default, which is what the
#: large majority of repositories in the corpus configure.
DEFAULT_LINE_LIMIT: Final[int] = 88

#: Parameters that carry no useful annotation signal.
_IMPLICIT_PARAMS: Final[frozenset[str]] = frozenset({"self", "cls"})

Counts = tuple[int, int]
_FuncDef = (ast.FunctionDef, ast.AsyncFunctionDef)


def _parse(source: str) -> ast.Module | None:
    """Parse source, returning None when it is not valid Python.

    Corpus files span years of real repositories, so syntax errors and null bytes
    are expected rather than exceptional. Those files are skipped, not counted.
    """
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError):
        return None


def type_hint_coverage(source: str) -> Counts | None:
    """Fraction of functions carrying at least one annotation.

    A function counts as annotated if it has a return annotation or any annotated
    parameter, ignoring ``self`` and ``cls``.

    Args:
        source: Python source text.

    Returns:
        ``(annotated, total)``, or None if the source does not parse.

    """
    tree = _parse(source)
    if tree is None:
        return None
    annotated = total = 0
    for node in ast.walk(tree):
        if not isinstance(node, _FuncDef):
            continue
        total += 1
        params = [
            a
            for a in (*node.args.args, *node.args.kwonlyargs, *node.args.posonlyargs)
            if a.arg not in _IMPLICIT_PARAMS
        ]
        if node.returns is not None or any(a.annotation for a in params):
            annotated += 1
    return annotated, total


def docstring_coverage(source: str) -> Counts | None:
    """Fraction of public functions and classes carrying a docstring.

    Names beginning with an underscore are treated as private and excluded, which
    matches how pydocstyle and Ruff's D rules are configured by default.

    Args:
        source: Python source text.

    Returns:
        ``(documented, total)``, or None if the source does not parse.

    """
    tree = _parse(source)
    if tree is None:
        return None
    documented = total = 0
    for node in ast.walk(tree):
        if not isinstance(node, (*_FuncDef, ast.ClassDef)):
            continue
        if node.name.startswith("_"):
            continue
        total += 1
        if ast.get_docstring(node):
            documented += 1
    return documented, total


def line_length_compliance(source: str, limit: int = DEFAULT_LINE_LIMIT) -> Counts | None:
    """Fraction of lines within the length limit.

    Args:
        source: File text.
        limit: Maximum permitted line length.

    Returns:
        ``(within_limit, total_lines)``, or None for an empty file.

    Raises:
        ValueError: If limit is not positive.

    """
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    lines = source.splitlines()
    if not lines:
        return None
    return sum(1 for line in lines if len(line) <= limit), len(lines)


#: Rule family name -> metric function.
METRICS: Final[dict[str, object]] = {
    "type_hints": type_hint_coverage,
    "docstrings": docstring_coverage,
    "line_length": line_length_compliance,
}
