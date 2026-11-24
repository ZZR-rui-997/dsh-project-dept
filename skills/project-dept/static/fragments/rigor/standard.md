# Rigor: standard

The result enters a formal deliverable but a mistake can still be corrected later. This is the default.

## What applies

- **L1 self-check** against the declared acceptance standard, ticked item by item in a separate file.
- **L2 independent review** on the primary artefact. The reviewer gets the artefact and the acceptance standard, not the author's reasoning. It writes its own conclusion first.
- **L3 Lead judgement**, including one thing the Lead checks itself.
- **Baseline sampling**: at least a handful of the baselines used get traced back to their original source. See `references/provenance-and-baseline.md`.

## The blind package

Build it as: artefact(s) + declared acceptance standard + the minimum context to judge. Strip the author's self-check, summary of conclusions, and any hints about what the author expects to be found.

The reviewer's brief must not include the Lead's hypothesis about what is wrong — that turns an independent review into a confirmation exercise.

## Sampling discipline

The Lead chooses what gets sampled. Choose it **before** looking at the artefact, and choose the hardest-to-verify items rather than the easy ones. If the sample is picked after reading the artefact, it will drift toward what looks checkable.

## What counts as evidence

Independent recomputation > external authority (published value, analytic solution, standard clause) > internal consistency (dimensions, limits, conservation) > "it satisfies the requirement".

Not evidence, under any circumstances: "same as the previous version", "matches our earlier audited value", "the author says it runs", "the file exists", "looks reasonable", "same order of magnitude".
