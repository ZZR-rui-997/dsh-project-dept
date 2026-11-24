# Provenance and the baseline

## Why this file exists

The most dangerous error is not a wrong number. It is a wrong **ruler** — a number, definition, or list that everyone uses to judge correctness, and which is itself wrong. Everyone then checks diligently against the same wrong ruler, and the error propagates in perfect agreement.

The failure mode is quiet: an internal summary gets compiled once, gets quoted a few times, and by the third citation it is being used as if it came from the original data.

## Four provenance classes

| class | meaning | may be a baseline? |
|---|---|---|
| `[Origin]` | original data or original file, plus a locator (file:line, table, page) that can be re-checked | yes |
| `[External]` | published value, analytic solution, standard clause, official document | yes |
| `[Own]` | our own compiled notes, comparison tables, matrices, "previously audited" values, writing-style cards | **no — a claim to be verified** |
| `[None]` | recollection, "someone said", "we agreed earlier" | no — not usable at all |

Rule: anything used as an acceptance baseline or written into a formal deliverable carries a class and a locator. Without a locator it is `[None]` by definition, no matter how plausible it looks.

**Upgrading `[Own]` to `[Origin]` has exactly one path**: recompute it from the original data or original code and record how. "It matches our other summary" is not an upgrade — two summaries can back the same mistake.

## Baseline register

Keep an explicit register of every item currently used as a baseline, one row each: item, value/definition, locator, class, status (`ok` / `[untraced]` / `conflicting` / `stale`).

This register is a deliverable in its own right. A project with 200 correct numbers and an unregistered wrong ruler is in worse shape than a project with 20 numbers and a clean register.

## When a baseline turns out to be wrong

Do it in this order, and do not skip step 2:

1. **Stop downstream work** that depends on it. Immediately — not after the current run finishes.
2. **Map the blast radius**: which delivered artefacts already used it? Which are in flight?
3. **Register the impact** as debts, one per affected artefact, with what needs redoing.
4. **Fix the baseline itself** — including the place it was first written down (it is usually one summary file plus everything that quoted it).
5. **Re-run the affected parts** and mark the old results superseded. Do not delete them; a superseded result with a reason is evidence, a deleted one is a gap.

## The four shapes this goes wrong in practice

1. **A statistic with no fixed definition.** A correlation length quoted to four digits that reproduces only under one unstated convention, and not under the definition actually in the code.
2. **A limit that was never checked against the run.** A Courant limit stated in the matrix that the solver's actual setting violates once the time step is chosen.
3. **An aspect ratio or count copied from a plan, never measured.** The plan said 14.2; the artefact measures 7.5.
4. **A count with several live versions.** The reference list is described as 15, 13, 11, and 11 in four places, and nobody decided which is the baseline.

All four share a mechanism: **an `[Own]` summary used as `[Origin]`**.

## A fifth shape, about status rather than numbers

"We already finalised that part" is also a baseline, and it is `[Own]` too. A completion or freeze status must be confirmed by the human who owns the decision before any downstream work treats it as settled. When the human later says "that was never final", the whole chain that relied on it is invalidated — including decisions like "no need to run the checker here".
