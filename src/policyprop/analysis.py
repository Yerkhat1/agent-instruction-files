"""Statistics over the measured corpus.

The corpus is one record per (repository, rule family). Each record holds
compliance before the rule and at HEAD, split by whether anything edited the file
afterwards. Everything below is derived from those records.
"""

from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Final

log = logging.getLogger(__name__)

#: A rule is "ceremonial" when the code already satisfied it this well on the day
#: it was written down. Rules above this line cannot move much by construction.
CEILING: Final[float] = 0.90

#: Instances with less headroom than this are dropped from the headroom analysis,
#: where the denominator would otherwise be near zero and the ratio meaningless.
MIN_HEADROOM: Final[float] = 0.02

PERMUTATIONS: Final[int] = 20_000
BOOTSTRAP_RESAMPLES: Final[int] = 4_000
SEED: Final[int] = 20260908

GROUPS: Final[tuple[str, str]] = ("touched", "untouched")
PHASES: Final[tuple[str, str]] = ("before", "after")


@dataclass(frozen=True, slots=True)
class Instance:
    """One rule in one repository, measured at two revisions."""

    repo: str
    family: str
    tool_backed: bool
    before: float
    after: float
    contact: float

    @property
    def delta(self) -> float:
        """Change in whole-tree compliance, in proportion points."""
        return self.after - self.before

    @property
    def headroom(self) -> float:
        """Compliance that was available to gain when the rule was written."""
        return 1.0 - self.before

    @property
    def captured(self) -> float:
        """Share of the available headroom the rule actually closed.

        Raises:
            ZeroDivisionError: If the instance started at full compliance.

        """
        return self.delta / self.headroom

    @property
    def ceremonial(self) -> bool:
        """True if the rule was written against code that already complied."""
        return self.before >= CEILING


def _pooled(record: dict[str, object], phase: str) -> float | None:
    """Weighted compliance across touched and untouched files at one revision."""
    numerator = denominator = 0.0
    for group in GROUPS:
        value = record.get(f"{group}_{phase}")
        count = record.get(f"{group}_{phase}_n")
        if not isinstance(value, (int, float)) or not isinstance(count, (int, float)):
            continue
        if not count:
            continue
        numerator += float(value) * float(count)
        denominator += float(count)
    return numerator / denominator if denominator else None


def load_instances(path: str | Path) -> list[Instance]:
    """Read measures.jsonl into Instance records.

    Records missing a usable compliance figure at either revision are skipped and
    counted in the log rather than silently dropped.

    Args:
        path: Path to the line-delimited JSON corpus.

    Returns:
        Every usable instance, in file order.

    Raises:
        FileNotFoundError: If the corpus file is absent.

    """
    path = Path(path)
    instances: list[Instance] = []
    skipped = 0
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                log.warning("%s:%d is not valid JSON, skipping", path.name, line_no)
                skipped += 1
                continue
            before, after = _pooled(record, "before"), _pooled(record, "after")
            survivors = record.get("n_survivors") or 0
            if before is None or after is None or not survivors:
                skipped += 1
                continue
            instances.append(
                Instance(
                    repo=str(record["repo"]),
                    family=str(record["family"]),
                    tool_backed=bool(record["tool_backed"]),
                    before=before,
                    after=after,
                    contact=float(record.get("n_touched", 0)) / float(survivors),
                )
            )
    if skipped:
        log.info("skipped %d unusable record(s) in %s", skipped, path.name)
    return instances


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean.

    Raises:
        ValueError: If values is empty.

    """
    if not values:
        raise ValueError("mean of no values")
    return sum(values) / len(values)


def prescriptive(instances: Iterable[Instance]) -> list[Instance]:
    """Instances that asked for real change and had room to show it."""
    return [i for i in instances if not i.ceremonial and i.headroom > MIN_HEADROOM]


def stratified_permutation_p(
    instances: Sequence[Instance],
    attribute: str,
    draws: int = PERMUTATIONS,
    seed: int = SEED,
) -> tuple[float, float]:
    """Permutation test on tool-backed vs declaration-only, shuffled within family.

    Family composition differs between the two arms, and line-length rules sit near
    ceiling almost everywhere, so a global shuffle would test family mix as much as
    tool backing. Shuffling inside each family removes that.

    Args:
        instances: The instances to test.
        attribute: Instance attribute to compare, e.g. "captured".
        draws: Number of permutations.
        seed: Random seed, fixed so results are reproducible.

    Returns:
        ``(observed_difference, p_value)``.

    Raises:
        ValueError: If either arm is empty.

    """
    rng = random.Random(seed)
    backed = [getattr(i, attribute) for i in instances if i.tool_backed]
    plain = [getattr(i, attribute) for i in instances if not i.tool_backed]
    if not backed or not plain:
        raise ValueError("both arms must be non-empty")
    observed = mean(backed) - mean(plain)

    by_family: dict[str, list[Instance]] = defaultdict(list)
    for instance in instances:
        by_family[instance.family].append(instance)

    extreme = 0
    for _ in range(draws):
        shuffled_backed: list[float] = []
        shuffled_plain: list[float] = []
        for members in by_family.values():
            labels = [i.tool_backed for i in members]
            rng.shuffle(labels)
            for instance, label in zip(members, labels, strict=True):
                target = shuffled_backed if label else shuffled_plain
                target.append(getattr(instance, attribute))
        if shuffled_backed and shuffled_plain:
            diff = mean(shuffled_backed) - mean(shuffled_plain)
            if abs(diff) >= abs(observed):
                extreme += 1
    return observed, extreme / draws


def clustered_bootstrap_ci(
    instances: Sequence[Instance],
    attribute: str,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = SEED,
) -> tuple[float, float]:
    """95% interval for the tool-backed minus declaration-only difference.

    Resamples whole repositories, since one repository can contribute several rule
    instances and those are not independent.

    Returns:
        ``(low, high)`` bounds of the 95% interval.

    """
    rng = random.Random(seed)
    by_repo: dict[str, list[Instance]] = defaultdict(list)
    for instance in instances:
        by_repo[instance.repo].append(instance)
    repos = list(by_repo)

    diffs: list[float] = []
    for _ in range(resamples):
        sample: list[Instance] = []
        for _ in repos:
            sample.extend(by_repo[rng.choice(repos)])
        backed = [getattr(i, attribute) for i in sample if i.tool_backed]
        plain = [getattr(i, attribute) for i in sample if not i.tool_backed]
        if backed and plain:
            diffs.append(mean(backed) - mean(plain))
    diffs.sort()
    return diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


def summarize(instances: Sequence[Instance]) -> dict[str, object]:
    """Headline figures for the whole corpus."""
    ceremonial = [i for i in instances if i.ceremonial]
    pres = prescriptive(instances)
    backed = [i for i in pres if i.tool_backed]
    plain = [i for i in pres if not i.tool_backed]
    return {
        "instances": len(instances),
        "repositories": len({i.repo for i in instances}),
        "ceremonial_share": len(ceremonial) / len(instances) if instances else 0.0,
        "mean_baseline": mean([i.before for i in instances]) if instances else 0.0,
        "prescriptive": len(pres),
        "captured_tool_backed": mean([i.captured for i in backed]) if backed else 0.0,
        "captured_declaration_only": mean([i.captured for i in plain]) if plain else 0.0,
        "captured_median_tool_backed": median([i.captured for i in backed]) if backed else 0.0,
        "contact_tool_backed": mean([i.contact for i in backed]) if backed else 0.0,
        "contact_declaration_only": mean([i.contact for i in plain]) if plain else 0.0,
    }
