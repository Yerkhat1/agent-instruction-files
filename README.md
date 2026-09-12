# Agent instruction files: what the rules in CLAUDE.md and AGENTS.md actually do

Repositories now ship a prose file, `CLAUDE.md` or `AGENTS.md`, that tells an AI coding assistant how to behave in that project. People treat these files as governance: write a rule down and the assistant follows it. This repository measures whether that holds, using 753 rule instances from 410 public Python repositories.

Compliance is computed by static analysis (Python AST traversal and line scanning) at two points: the commit where the rule first appears, and the current head. No language model scores or judges anything.

## Findings

**Most rules record existing practice.** Two thirds of the rules were written against code that already met them at 90% or better. It depends heavily on the kind of rule.

| rule family | instances | compliance before the rule | already at 90%+ | change after |
|---|---|---|---|---|
| line length | 255 | 97.1% | 98% | −0.05 pts |
| type annotations | 393 | 83.6% | 56% | +1.45 pts |
| docstrings | 105 | 69.2% | 30% | +1.63 pts |
| all | 753 | 86.2% | 67% | +0.97 pts |

**When a rule asks for change, enforcement matters more than reach.** For the 251 rules that started below 90%, rules backed by a linter or type checker closed 10.2% of the remaining gap. Rules that existed only as prose closed 3.6%.

| | tool-backed (142) | prose only (109) | p |
|---|---|---|---|
| share of files edited after the rule | 0.472 | 0.516 | 0.38 |
| share of remaining gap closed | 10.21% | 3.64% | 0.022 |

The p-values come from 20,000 permutations with labels shuffled within each rule family. A bootstrap that resamples whole repositories puts the difference at 6.6 points, 95% interval 0.7 to 12.6.

Both groups edited a similar share of their files. The difference is in what happened to a file once it was opened: a formatter or type checker applies the rule to anything it touches, while an assistant editing a file for some other reason mostly leaves the prose rule unapplied.

**Limits.** This comparison is observational, not randomized. Projects that configure linters differ from projects that don't in ways this data can't see. The gap-closed distribution is skewed (median 0.81% vs 0%), so a minority of instances drives the means. The three rule families measured here are exactly the ones for which tooling already exists.

## Layout

| path | contents |
|---|---|
| `data/measures.jsonl` | one record per rule instance: repository, rule family, tool-backed flag, rule date, file counts, compliance before and after for edited and unedited files |
| `data/classified_repos.jsonl` | the classified corpus. 24 records marked `reconstructed_from_measures` were rebuilt from the measurement rows after their original classification file was lost; their instruction-file path is unknown |
| `pipeline/01_discover_classify.py` | finds and classifies repositories through the GitHub API |
| `pipeline/02_measure.py` | clones each repository with blobs filtered and measures compliance at both revisions |
| `analysis/final_inference.py` | every statistic above |
| `verify_numbers.py` | recomputes the headline figures from `data/measures.jsonl` and exits non-zero if any disagree |

## Reproduce

Standard-library Python only.

```bash
python3 verify_numbers.py
python3 analysis/final_inference.py
```

Re-running the pipeline needs an authenticated `gh` CLI and hits live GitHub. Repositories and search results change over time, so a fresh run will not match the released data exactly. The files in `data/` are the corpus the results are computed on.

## A measurement trap worth knowing about

Two tempting designs give clean and meaningless results. If the outcome is a marker the rule itself introduces, its value before the rule is zero by construction. And if you split files into edited and unedited and use the unedited ones as a control, their change is zero by construction too, because an unmodified file is byte-identical at both revisions. This project fell into both before catching them.

## Paper

A manuscript is under preparation. The full text will be added here after its first review.

## AI use

Yerkhat Takatbek chose the question, rejected weaker versions of it, and reviewed each result before keeping it. An AI assistant wrote the collection and analysis code, ran it, did the literature search, and drafted the text. No number was produced or adjusted by a model: every figure comes from logged runs over public data, and `verify_numbers.py` recomputes them.

## License

Code: MIT. Data: CC BY 4.0. The measurements are derived from public repositories; each repository's own license applies to its contents.
