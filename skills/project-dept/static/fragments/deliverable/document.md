# Deliverable: document

A text artefact someone reads end to end: chapter, report, proposal, slides, thesis section.

## Checks that matter

1. **Structure is continuous** — section numbers, figure numbers, table numbers, equation numbers run without gaps and without duplicates. Do not count by hand; run the bundled checker.
2. **Every caption is referenced, every reference has a caption** — bidirectional, both directions.
3. **The reference list and the in-text citations match in both directions** — nothing cited but missing, nothing listed but never cited. Both numbering style `[n]` and author–year style `(Author, Year)` must be handled; a checker that silently skips one style is worse than no checker (it reports PASS on nothing).
4. **Terminology is written the same way everywhere** — the banned-variant list lives in project config, never inside the script.
5. **Numbers in the text match the numbers in the tables/figures** — the checker cannot decide this; the reviewer must spot-check the headline numbers against the artefact that produced them.

## Review emphasis

- L2 reviewer reads the document as a stranger: does each claim follow from the evidence shown in the document itself?
- Confirm the acceptance standard was not quietly weakened (e.g. "chapter done" redefined as "chapter drafted").
- A document that passes all mechanical checks can still be wrong; say which semantic claims were not verified.

## Common traps

- Chapter/section detection from body text instead of heading styles — table cells containing `1.6 mm` get read as a section number and produce fake failures.
- Author–year citations are invisible to a checker written only for `[n]`.
- Surname extraction by splitting on commas — a reference like `Brown S R. Simple model...` becomes one giant token and every citation is reported as missing.
- Multi-author citations joined by a conjunction ("A 与 B (1979)") — the second author must be registered as an alias.
