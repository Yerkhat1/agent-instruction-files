"""The statistics decide the paper's claims, so the arithmetic is pinned down."""

import json

import pytest

from policyprop.analysis import (
    CEILING,
    Instance,
    clustered_bootstrap_ci,
    load_instances,
    mean,
    prescriptive,
    stratified_permutation_p,
    summarize,
)


def make(repo="r", family="type_hints", tool=True, before=0.5, after=0.6, contact=0.5):
    return Instance(
        repo=repo, family=family, tool_backed=tool, before=before, after=after, contact=contact
    )


def test_delta_and_headroom():
    i = make(before=0.40, after=0.55)
    assert i.delta == pytest.approx(0.15)
    assert i.headroom == pytest.approx(0.60)
    assert i.captured == pytest.approx(0.25)


def test_ceremonial_boundary_is_inclusive():
    assert make(before=CEILING).ceremonial
    assert not make(before=CEILING - 0.001).ceremonial


def test_prescriptive_excludes_ceiling_and_thin_headroom():
    rows = [make(before=0.95), make(before=0.99), make(before=0.50)]
    assert len(prescriptive(rows)) == 1


def test_pooled_compliance_weights_by_file_count(tmp_path):
    # 1.0 over 10 units and 0.0 over 30 units pools to 0.25, not 0.5.
    record = {
        "repo": "a/b",
        "family": "type_hints",
        "tool_backed": True,
        "n_survivors": 4,
        "n_touched": 2,
        "touched_before": 1.0,
        "touched_before_n": 10,
        "untouched_before": 0.0,
        "untouched_before_n": 30,
        "touched_after": 1.0,
        "touched_after_n": 40,
    }
    path = tmp_path / "m.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    (one,) = load_instances(path)
    assert one.before == pytest.approx(0.25)
    assert one.after == pytest.approx(1.0)
    assert one.contact == pytest.approx(0.5)


def test_loader_skips_unusable_records(tmp_path):
    good = {
        "repo": "a/b",
        "family": "docstrings",
        "tool_backed": False,
        "n_survivors": 1,
        "n_touched": 1,
        "touched_before": 0.5,
        "touched_before_n": 2,
        "touched_after": 0.5,
        "touched_after_n": 2,
    }
    no_counts = {**good, "repo": "c/d", "touched_before_n": 0, "touched_after_n": 0}
    path = tmp_path / "m.jsonl"
    path.write_text(
        "\n".join([json.dumps(good), "not json", json.dumps(no_counts), ""]), encoding="utf-8"
    )
    assert [i.repo for i in load_instances(path)] == ["a/b"]


def test_permutation_is_reproducible_and_detects_a_real_split():
    rows = [make(repo=f"t{i}", tool=True, before=0.5, after=0.9) for i in range(12)]
    rows += [make(repo=f"p{i}", tool=False, before=0.5, after=0.5) for i in range(12)]
    first = stratified_permutation_p(rows, "captured", draws=2000)
    second = stratified_permutation_p(rows, "captured", draws=2000)
    assert first == second
    observed, p_value = first
    assert observed > 0
    assert p_value < 0.05


def test_permutation_finds_nothing_when_arms_are_identical():
    rows = [make(repo=f"t{i}", tool=i % 2 == 0, before=0.5, after=0.6) for i in range(12)]
    _, p_value = stratified_permutation_p(rows, "captured", draws=500)
    assert p_value == pytest.approx(1.0)


def test_permutation_needs_both_arms():
    with pytest.raises(ValueError, match="non-empty"):
        stratified_permutation_p([make(tool=True)], "captured", draws=10)


def test_bootstrap_interval_brackets_the_point_estimate():
    # Give the arms spread; identical values make every resample equal and the
    # interval collapse to a point, which is a property of the fixture, not the code.
    rows = [make(repo=f"t{i}", tool=True, before=0.5, after=0.80 + 0.01 * i) for i in range(10)]
    rows += [make(repo=f"p{i}", tool=False, before=0.5, after=0.50 + 0.01 * i) for i in range(10)]
    backed = mean([r.captured for r in rows if r.tool_backed])
    plain = mean([r.captured for r in rows if not r.tool_backed])
    point = backed - plain
    low, high = clustered_bootstrap_ci(rows, "captured", resamples=400)
    assert low <= point <= high
    assert low > 0


def test_bootstrap_on_identical_values_returns_a_point_interval():
    rows = [make(repo=f"t{i}", tool=True, before=0.5, after=0.9) for i in range(6)]
    rows += [make(repo=f"p{i}", tool=False, before=0.5, after=0.5) for i in range(6)]
    low, high = clustered_bootstrap_ci(rows, "captured", resamples=200)
    assert low == pytest.approx(high)
    assert low == pytest.approx(0.8)


def test_mean_rejects_empty():
    with pytest.raises(ValueError):
        mean([])


def test_summarize_reports_shares():
    rows = [make(before=0.95), make(before=0.95), make(before=0.5, tool=False)]
    stats = summarize(rows)
    assert stats["instances"] == 3
    assert stats["ceremonial_share"] == pytest.approx(2 / 3)
