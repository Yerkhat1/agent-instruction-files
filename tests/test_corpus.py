"""The released corpus must keep reproducing the figures in the manuscript."""

from pathlib import Path

import pytest

from policyprop.analysis import load_instances, summarize
from policyprop.cli import PAPER_FIGURES

CORPUS = Path(__file__).resolve().parents[1] / "data" / "measures.jsonl"


@pytest.fixture(scope="module")
def stats():
    if not CORPUS.exists():
        pytest.skip("corpus not present")
    return summarize(load_instances(CORPUS))


@pytest.mark.parametrize(
    ("key", "expected", "tolerance"), [(k, v[0], v[1]) for k, v in PAPER_FIGURES.items()]
)
def test_published_figure_still_holds(stats, key, expected, tolerance):
    assert abs(float(stats[key]) - expected) <= tolerance
