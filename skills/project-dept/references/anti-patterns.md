# Anti-patterns

Each entry below is a failure that actually happened and cost real time. They are listed in the form "behaviour → what it looks like from inside → why it fails".

## Delivery and acceptance

- **Executor marks its own task complete** → looks like efficiency → the acceptance step silently disappears, and "done" now means "produced something".
- **Reviewer sees the author's self-check first** → looks like being thorough → it gets anchored, and reviews become confirmations.
- **Reviewer shares the author's inputs or assumptions** → looks like consistency → shared inputs produce shared blind spots; the review cannot see what both took for granted.
- **Acceptance standard written by the executor** → looks like delegation → the standard migrates toward what was actually produced.
- **"Delivery ≠ done" forgotten under time pressure** → looks like pragmatism → this is precisely the moment acceptance is worth most.

## Evidence

- **"Consistent with the previous version" used as proof** → looks like regression testing → it proves nothing changed, not that anything was right.
- **"Matches our earlier audited value" used as proof** → looks like cross-validation → the earlier audit is the very thing that may be wrong.
- **"It runs" used as proof** → looks like verification → running and being correct are unrelated.
- **"Same order of magnitude" used as proof** → looks like a sanity check → it passes for a wrong answer that is merely nearby.
- **A checker that reports PASS over an empty set** → looks like a green build → the worst outcome, because it buys false confidence. Prove the checker can fail.
- **Counting occurrences and calling it a count of unique items** → looks like precision → a number stated as N that is really an upper bound propagates as fact.

## Baselines

- **Internal summary promoted to baseline** → looks like using established results → the ruler is now unverified, and everyone checks against it.
- **A statistic quoted to 4 digits with no recorded definition** → looks like rigour → it reproduces under one unstated convention only.
- **Several live versions of the same count/variant** → looks like thorough documentation → nobody can tell which one is authoritative, so each downstream reader picks a different one.
- **"We finalised that already" treated as settled** → looks like respecting prior decisions → a completion status is also `[Own]` and must be confirmed by its owner.
- **Deleting superseded results** → looks like housekeeping → a superseded result with a reason is evidence; a deleted one is an unanswerable gap.

## Process and scope

- **Several modules in parallel** → looks like using the team well → conventions drift apart and rework stacks up.
- **"Just fix this small thing nearby while I'm here"** → looks like diligence → it breaks the frozen list and mixes two packages' acceptance.
- **Tasks created when no package is open** → looks like preparation → the board fills with orphans and the real package's tasks lose meaning.
- **Closing a package by deleting its tasks** → looks like cleanup → the task descriptions held the debts.
- **A debt ledger that only grows** → looks like honest bookkeeping → a debt with no disposition is a decision nobody made. Every debt must be closed, explicitly exempted with a review date, or downgraded with a reason.

## Rules and tooling

- **Adding a rule to prevent an imagined accident** → looks like foresight → nobody can tell whether it works, and it will be bypassed as bureaucracy.
- **A rule with no inapplicability clause** → looks like clarity → it gets applied to the case it was never meant for.
- **Improvising a role description instead of using the role card** → looks like adapting to the task → the same environment traps get re-learned every time.
- **A script with machine-specific absolute paths** → looks like it works → it works once, on one machine.
- **Switching to a capability-composition preset in order to tweak configuration** → looks like using the right tool → the new composition may be missing capabilities the work depends on (e.g. document-processing tools), and the loss is silent until it matters.
- **Solving a host limitation by inventing a workaround before reading the host's documentation** → looks like pragmatism → the mechanism usually already exists and only needs enabling.

## Reporting

- **Silence about what was not checked** → looks like confidence → the reader fills the silence with the assumption of full coverage.
- **Reviewer opinion written in the same voice as a verified fact** → looks like a decisive review → inference later gets quoted as evidence.
- **A summary that presents the pleasant conclusion and moves the inconvenient one into a footnote** → looks like good writing → the reader remembers the conclusion, not the caveat.
