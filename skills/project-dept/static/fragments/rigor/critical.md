# Rigor: critical

Irreversible, externally published, or becomes the baseline that later work checks itself against. A mistake here propagates silently into everything downstream.

## What applies

Everything in `standard.md`, plus:

- **Two-stage review.** First a mechanical pass (scriptable checks, citations, reproducibility), then a judgement pass by a reviewer with domain competence. A mechanical pass alone never closes a critical package.
- **Baseline re-check is mandatory, not sampled 1/3 but *all* baselines that the conclusion directly rests on.** Anything that cannot be traced is demoted to `[Own]` and the claim is weakened accordingly, in writing.
- **Direction pre-mortem is mandatory and must be written, not thought.** See `references/self-skepticism.md`.
- **The Lead's own probe is mandatory and must be independent of the reviewer's method** — if the reviewer recomputed, the Lead checks against an external authority or vice versa.
- **Explicit sign-off.** The user (or the responsible human) approves before the artefact leaves the department. Do not substitute your own approval.

## Review independence, hard form

- The reviewer must not be the author, must not have contributed to the artefact, and must not have been present while it was made.
- The reviewer's inputs are built by someone other than the author where possible.
- If the same reviewer reviews several critical packages in a row on the same subject, note it — repeated review by the same person converges on "confirmed", not "checked".

## Panel review trigger

Convene a **panel** (2–3 reviewers with distinct anchor methods) instead of a single reviewer when: the artefact will become a baseline other work checks against; a prior review on this subject missed something material; the user asks for it; or the Lead-controlled weaknesses (package assembly, brief, sampling) cannot otherwise be mitigated here. Composition, independence, and verdict rules: see `references/blind-review.md` § Panel review.

## What to write down that feels excessive

- Which baselines were re-checked, against what original, on what date.
- Which claims were **not** verified, and why that is acceptable.
- What would falsify the central conclusion, and whether anyone tried.

## Honest limitation to state

An independent review can check "is this number right". It cannot check "should the model have been built this way at all". Method-level errors survive every review that shares the same materials. For those, the only defences are external authority, a falsification attempt, and the human sign-off — say so rather than implying the review covered it.
