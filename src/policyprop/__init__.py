"""Measuring whether rules in agent instruction files change code compliance."""

from policyprop.analysis import Instance, load_instances, summarize
from policyprop.metrics import docstring_coverage, line_length_compliance, type_hint_coverage

__all__ = [
    "Instance",
    "docstring_coverage",
    "line_length_compliance",
    "load_instances",
    "summarize",
    "type_hint_coverage",
]
__version__ = "0.1.0"
