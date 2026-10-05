"""Command line entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from policyprop.analysis import (
    clustered_bootstrap_ci,
    load_instances,
    prescriptive,
    stratified_permutation_p,
    summarize,
)

DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / "data" / "measures.jsonl"

#: Figures as printed in the manuscript, with the tolerance each is checked to.
PAPER_FIGURES: dict[str, tuple[float, float]] = {
    "instances": (753, 0),
    "repositories": (410, 0),
    "ceremonial_share": (0.67, 0.006),
    "mean_baseline": (0.862, 0.0006),
    "prescriptive": (251, 0),
    "captured_tool_backed": (0.1021, 0.0006),
    "captured_declaration_only": (0.0364, 0.0006),
    "contact_tool_backed": (0.472, 0.0006),
    "contact_declaration_only": (0.516, 0.0006),
}


def _report(corpus: Path) -> int:
    instances = load_instances(corpus)
    stats = summarize(instances)
    pres = prescriptive(instances)
    observed, p_value = stratified_permutation_p(pres, "captured")
    low, high = clustered_bootstrap_ci(pres, "captured")

    print(f"instances {stats['instances']}  repositories {stats['repositories']}")
    print(f"ceremonial (>= 90% compliance already) {stats['ceremonial_share']:.1%}")
    print(f"mean baseline compliance {stats['mean_baseline']:.1%}")
    print()
    print(f"prescriptive instances {stats['prescriptive']}")
    print(f"  headroom captured, tool-backed      {stats['captured_tool_backed']:+.2%}")
    print(f"  headroom captured, declaration-only {stats['captured_declaration_only']:+.2%}")
    print(f"  contact, tool-backed      {stats['contact_tool_backed']:.3f}")
    print(f"  contact, declaration-only {stats['contact_declaration_only']:.3f}")
    print()
    print(f"difference {observed:+.4f}  stratified permutation p = {p_value:.4f}")
    print(f"95% clustered bootstrap interval [{low:+.4f}, {high:+.4f}]")
    return 0


def _verify(corpus: Path) -> int:
    stats = summarize(load_instances(corpus))
    failures = 0
    for key, (expected, tolerance) in PAPER_FIGURES.items():
        actual = float(stats[key])  # type: ignore[arg-type]
        ok = abs(actual - expected) <= tolerance
        failures += not ok
        print(f"[{'OK' if ok else 'XX'}] {key:<28} paper={expected} got={actual:.4f}")
    print(f"\n{len(PAPER_FIGURES) - failures}/{len(PAPER_FIGURES)} figures verified")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Returns:
        0 on success, 1 if verification found a mismatch.

    """
    parser = argparse.ArgumentParser(
        prog="policyprop",
        description="Measure whether rules in agent instruction files change compliance.",
    )
    parser.add_argument("command", choices=("report", "verify"))
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS,
        help="path to measures.jsonl (default: the released corpus)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    if not args.corpus.exists():
        parser.error(f"corpus not found: {args.corpus}")
    return _report(args.corpus) if args.command == "report" else _verify(args.corpus)


if __name__ == "__main__":
    sys.exit(main())
