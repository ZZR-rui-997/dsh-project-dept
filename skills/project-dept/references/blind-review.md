# Organising an independent review

An independent review answers one question: **does the artefact hold up when read by someone who owes the author nothing?**

It does not answer "is the overall approach right". Read that limitation first and keep it in mind; most disappointment with review comes from expecting the second thing.

## Building the blind package

Put into the package directory:

- the artefact itself, complete and unedited;
- the declared acceptance standard;
- the minimum context needed to judge (input data, the specification it must meet).

Leave out:

- the author's self-check;
- the author's summary of conclusions;
- anything that says what the author expects to be found;
- conversation history that reveals the author's reasoning.

If you are the Lead and you built the package, that is itself a weakness: you may unconsciously leave out what makes you look bad. Note it, and when the package matters, have someone else assemble it.

## Briefing the reviewer

State:

- what is being reviewed, and against which acceptance standard;
- what the reviewer must produce (a written conclusion, and at least one real problem found);
- the anchor priority (below);
- the prohibition list (below);
- that finding nothing requires writing down what was actually recomputed and why it was fine.

Do **not** state: what you suspect is wrong, which sections you are unsure about, or what a good outcome looks like. That converts independent review into confirmation.

## Anchor priority

1. **Independent recomputation** — the reviewer's own calculation from the original input.
2. **External authority** — published value, analytically derived solution, standard clause, official document.
3. **Internal consistency** — dimensions balance, limits behave, conservation holds.
4. **Requirement baseline** — can only establish "meets the requirement", never "is correct".

## Not evidence, ever

- "same as the previous version";
- "matches our earlier audited value";
- "the author says it runs";
- "the file exists";
- "looks reasonable";
- "the same order of magnitude".

## Review discipline

- Write the conclusion **before** opening the author's self-check. Afterwards is not a review, it is a proofread.
- Default assumption: there is something wrong. Find at least one real problem, or document what you recomputed.
- Do not share the author's inputs or assumptions if you can avoid it — shared inputs produce shared blind spots.
- The sample of things to re-check is chosen by the Lead in advance, biased toward the hardest-to-verify items.

## Reporting

Separate three things, never mixed:

1. what the artefact says;
2. what the evidence supports;
3. what the reviewer infers or suspects.

Mark inference as inference. A reviewer's opinion stated in the same voice as a verified fact is how wrong opinions get promoted to baselines later.

## Known structural weaknesses — state them, do not hide them

- The Lead assembles the package, writes the brief, and picks the sample. All three are places where the review can be steered without anyone intending it.
- A reviewer with no domain competence can verify mechanics and miss meaning; a reviewer with too much shared history can verify meaning and miss nothing new.
- Repeated review by the same person converges on agreement.

Cheap mitigations that cost nothing: rotate reviewers across packages, have the reviewer state what it did *not* check, and record the reviewer's independent conclusion verbatim before any discussion.

## Panel review (multi-reviewer)

One reviewer is the default. A **panel** (2–3 independent reviewers) is the upgrade when the cost of a missed error is high. It costs roughly N× one review, so convene it on triggers, not routinely:

- the artefact will become a baseline that later work checks itself against (critical rigour + baseline role);
- a previous review on this subject **missed something material** — a panel is the standing correction for a demonstrated blind spot;
- the user explicitly asks for it;
- the three Lead-controlled weaknesses above cannot otherwise be mitigated for this package.

Composition rules:

- **Different methods, not more of the same.** Assign each reviewer a different anchor: one recomputes, one checks against external authority, one works internal consistency. A panel that shares one method shares one blind spot — volume without diversity adds cost, not coverage.
- Optionally designate one reviewer as **devil's advocate**: their brief explicitly instructs attacking the conclusion, so "find nothing" is not an available outcome.
- **No cross-visibility.** Every reviewer writes an independent conclusion before seeing any other reviewer's conclusion; after all are written, the Lead compares them and records agreements and divergences.
- **No shared inputs.** Do not let reviewers share inputs, assumptions, or the Lead's suspicions — shared material produces convergent blind spots, which defeats the entire point of a panel.
- **Isolation on a shared filesystem is procedural, not enforced.** (R3-P5) The host may not guarantee sandboxing between reviewers, so the Lead must make isolation true by construction: each reviewer writes its 复核单 into its own subdirectory (`review/<task>/R1/`、`R2/`…), receives the package path only (never siblings' paths), and the brief explicitly forbids reading other reviewers' files. If a reviewer's tooling can read the whole workspace anyway, say so in the brief and treat the panel as "weak isolation" — rely on different anchor methods (which cannot be copied) rather than on invisibility alone.
- **Record the roster.** Who reviewed what, with which method, on which date — into the board. Rotation across packages is what keeps the panel from converging over time.

Verdict rules:

- Any single real problem found by any reviewer blocks the package.
- Unanimous PASS still requires the Lead's own L3 probe and, for critical rigour, explicit human sign-off. A panel lowers the probability of a missed error; it does not eliminate the method-level blind spot (see the honest limitation in `static/fragments/rigor/critical.md`).
- Divergent conclusions are information, not noise: record what each reviewer checked and reconcile explicitly, in writing.

Costly mitigations — only adopt them after a real incident justifies them: script-generated packages, Lead forbidden from writing the brief, two-level sampling. Do not adopt them speculatively; a rule that exists to prevent an imagined accident is a rule that will be resented and eventually bypassed.
