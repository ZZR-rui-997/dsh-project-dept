# Core principles

Run one work package at a time and make every hand-over survive an outsider's inspection.

## Non-negotiable stance

- **Delivered is not done.** Only the Lead closes a work package, and only after L1 self-check, L2 independent review, and L3 final judgement.
- **Independence is not a courtesy.** The reviewer must not be the author, must not share the author's inputs or assumptions, and must form a written conclusion before seeing the author's self-check.
- **The ruler is also a suspect.** Any number, definition, threshold, or list used as an acceptance baseline is itself subject to review; a tidy-looking internal summary is not a baseline.
- **No invented content.** Every number carries a source (`file:line`, table, page, or a reproducible command). Unverified is written as unverified, never as verified.
- **Reversibility beats cleverness.** Prefer rules whose failure mode is "one more unused file" over rules whose failure mode is "data or evidence is gone".
- **Serial over parallel.** One active work package; parallelism is allowed inside it, never across packages.
- **Write the acceptance standard before starting.** An acceptance standard that cannot be judged pass/fail is not an acceptance standard.

## Scope

Produce or verify exactly the artefacts the work package declared. Do not add:

- extra chapters/sections/features nobody asked for;
- "nice to have" cleanup of neighbouring material;
- corrections to other work packages noticed along the way — record them as debts instead.

## Language

Match the language the user works in. Keep identifiers (file names, commands, function names, flags, symbols) in their canonical form even inside prose in another language.

## Required provenance classes

Separate content into:

- `[Origin]` — comes straight from original data or an original file, with a locator that can be re-checked;
- `[External]` — an external authority: published value, analytic solution, standard/spec clause, official document;
- `[Own]` — own compiled notes, tables, summaries, or previously "audited" values — treat as **to be verified**, never as an acceptance baseline;
- `[None]` — no source (recollection, "someone said", "we agreed earlier") — unusable for acceptance and unusable in a formal deliverable.

Never let an `[Own]` value silently act as `[Origin]`. Upgrading `[Own]` to `[Origin]` requires re-deriving it from the original data or original code and recording how.

## Applicability

Keep the six-step flow stable, but adapt the check depth to the `rigor` axis. An exploratory package does not need a full blind review; a critical package needs more than the default. Say plainly what you did not check instead of implying full coverage.
