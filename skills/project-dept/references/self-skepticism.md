# Self-skepticism: should this rule exist, and is the direction right

Two instruments. The first decides whether a new rule/file/check is worth existing. The second decides whether the current direction deserves continued investment. Both are cheap; both are skipped by default, which is why they need to be written down.

## 1. Admission test for any new rule

Before adding a rule, file, checklist item, hook, or automation, answer three questions **in writing**:

| # | question | fails when |
|---|---|---|
| 1 | Does the work it saves exceed the work it adds? | the answer is qualitative. Require a quantity: minutes added per occurrence vs. rework avoided. |
| 2 | Has the error it prevents **actually happened**, with a date and a concrete incident? | the justification is "so that we don't miss it later". That is an imagined error. |
| 3 | If it fails, is the consequence reversible? | it can lose data, delete evidence, or remove a recorded debt. Irreversible failure modes require a much higher bar. |

**One explicit exception to question 2:** if the *user* directly asks for the mechanism (not
"we might miss this later"), the basis may be recorded as "explicit user request" — but it must be
written as such, never dressed up as an incident, and the same place must say what would make you
withdraw the mechanism (e.g. "if a year passes and it never blocks a real problem, remove it").
A user request is a legitimate reason to spend effort; an invented incident is not.

Also require, in one line: **when does this rule not apply?** A rule without an inapplicability clause will be applied to the case it was never meant for, and then it earns its reputation as bureaucracy.

Apply the test to your own proposals first. Under this test, the following were correctly rejected in practice:

- a hand-maintained member registry — question 1 failed: the same information was already required in the header of every artefact, so the registry was a second copy destined to rot;
- an automatic "clean up finished tasks" prompt — question 3 failed: deleting tasks deletes the debts recorded in them;
- a schema-enforced output format for every role card — question 2 failed: none of the historical review findings were format problems;
- file-write hooks — question 1 failed: the interception cost was high and the incident had not occurred.

And these survived: a pre-start gate script, a mechanical document checker, provenance classes, role cards.

## 2. Direction pre-mortem

Required when closing a work package, and mandatory for `rigor: critical`.

Answer three questions **in the board or package record**, not in your head:

1. **If the central conclusion is wrong, where is it most likely wrong?** At least three items. "I can't think of anything" is not an answer. At least one item must point at method or assumption — not a typo, not an arithmetic slip. Examples of the right kind of answer: the two-phase model is not equivalent to the single-phase approximation; the inlet condition does not represent the real working condition; the interpolated parameter lies outside the range the source actually measured; the conclusion's scope is broader than the geometry/duration supports.
2. **What is the minimum falsification action for each?** One recomputation, one control case, one original reference checked, one question to the user. If a falsification action cannot be named, the item is decoration.
3. **Sunk-cost check.** Is anything being continued because it has already cost N hours / N pages rather than because the evidence supports it? Answer honestly.

## Why this is not optional

Directions do not get questioned by accident. Work that runs smoothly is exactly the work nobody stops to challenge. Documented history in one project: two live versions of the chapter structure coexisting for weeks with downstream work looking for justification in both, and a "known conclusion" used for days that an independent audit later reversed. Neither was an arithmetic error. Both were directions nobody had questioned.

## Cheapest useful version

If the full pre-mortem is too heavy, keep only question 1 with the "at least one method-level item" requirement. That single line catches the class of error that reviews systematically miss.
