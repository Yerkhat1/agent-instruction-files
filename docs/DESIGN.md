# Why the obvious measurement is wrong

Two designs for this study look correct, produce clean significant results, and
measure nothing. I used both before noticing. This note is here because the
published work in this area is exposed to the same two mistakes.

## 1. Measuring the rule with the rule's own notation

The first instrument counted a marker the rule introduces. A provenance rule in
the production system I started from requires that a fact carry `source_url`, a
`verified_on` date, and a quoted line. The obvious outcome is: how many facts
carry that marker?

The marker cannot exist before the rule that defines it. Compliance is therefore
exactly zero for every unit in every pre-adoption period, and any post-adoption
value produces a clean step. My first panel showed 0.00% for ten consecutive
weeks across 41 units, then a monotone rise. It looks like a textbook
interrupted time series. It measures the spread of a notation.

**Rule:** the outcome has to be definable identically on both sides of the
intervention. Here that is whether a line asserting a governed fact also carries
a source URL, which is well defined before and after and does move.

## 2. Using unmodified files as a control group

The second instrument split files into those edited after the rule and those
not, then used the unedited files as a control.

They are not a control. A file no commit touched is byte-identical at both
revisions, so its measured change is necessarily zero. An arm with zero variance
sitting next to an arm that moves looks like a clean effect and is circular.

The giveaway both times was the same: a control group with no variance and
unusually tidy numbers.

**Rule:** treat contact as part of the outcome rather than as something to
stratify on.

```
change in whole-tree compliance = (share of files touched) x (change among touched files)
```

Both factors carry information. The first is how far the policy reached, the
second is what it did on contact. Measuring only the second hides the thing that
turned out to matter.

## 3. Why labels are permuted inside each family

Line-length rules are declared at 97.1% compliance and 98% of them are already
at ceiling. Type-hint and docstring rules are not. The tool-backed and
declaration-only arms do not contain the same mix of families, so a global
shuffle would partly test family composition rather than tool backing.
`stratified_permutation_p` shuffles labels within each family, which removes
that confound. The repository-clustered bootstrap exists for a second reason:
one repository can contribute several rule instances and those are not
independent draws.

## 4. What this design still cannot do

Repositories that ship linter configuration differ from those that do not in
ways the data does not capture: team size, project maturity, how seriously the
project takes tooling at all. The comparison is observational. The coefficient
should be read as the difference between projects that mechanise policy and
projects that do not, which is wider than the effect of the mechanism itself.
