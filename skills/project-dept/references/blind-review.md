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

## Review cadence and token budget — three tiers (v1.3.0, P-14-1)

Reviewing *every* small task and reviewing *only* at closeout are both wrong. What decides the tier is **blast radius × irreversibility × how much changed this round**. Thresholds are hard numbers; do not eyeball them.

| Tier | When | Who | What they get | Budget |
|---|---|---|---|---|
| **A — incremental** (default) | closeout of one deliverable unit (one case, one section, one script change) | 1 reviewer | product + acceptance criteria + **previous review form** + this round's fix log/diff. Must answer: did the fix really land / did it break anything / recompute 3 numbers by hand | **≤3M tokens, ≤10 min** |
| **B — full panel** (mandatory) | ① every project-section closeout; ② any number that will enter the manuscript or be cited as a baseline by another section; ③ a criterion itself changed | **2 reviewers with different methods** (independent recompute / external authority / devil's advocate — pick two) | everything, **no sampling**, re-read from disk, **no author self-check, no fix log** | **≤30M tokens** |
| **C — triggered** | ① a baseline was changed ② a conclusion got reversed ③ you just caught a self-check miss ④ same error twice | 1 reviewer, one target | the point plus its direct downstream | **≤8M tokens** |
| **no review** | middleware: probe scripts, drafts, logs, read-only surveys, formatting tweaks | — | — | 0 |

**Why these cut-offs (our own numbers, not theory)**

1. **L1 self-check alone always misses something.** In one blind review, 8/8 findings were items the author had already ticked in self-check; a second one missed two hard errors (a mesh-arithmetic mix-up and a wrong step count) entirely. Self-check is not a substitute for any tier.
2. **A full review is expensive**: 13–28M tokens for one full pass (measured: 28.2M/59 min, 26.3M/1 h, 13.6M/24 min); an early small review ≈3.7M.
3. **Repeating full reviews per unit has diminishing returns**: 13 consecutive full rounds on this very package produced 12 → 26+9 → 26+10 → 6+7 → 5+5 → 2+4 → 1+4 → 4+2 → 3+2 → 3+3 → 2+2 → 2+3 → **0** findings, and the last rounds caught only documentation consistency. Repeating full reviews at unit frequency is pure burn.
4. **Incremental reviews are sufficient** for unit-level changes: given only "v2 product + previous review form + fix log", one review still caught 8 real issues (including "micro-rise described as monotone decline" and a percentage range that was actually 3.5–10.5%).

**Four engineering levers (cheaper than reviewing less)**

1. **Review the delta**, not everything: require the three answers above. Accumulated drift is covered by tier B.
2. **Script the criteria**: give the reviewer a runnable checker (`dept_gate.py`, `check_doc.py`, `check_skill.py`, `run_evals.py`). They run the script for the mechanical part, then hand-compute 3 numbers. This saves exploration tokens, not verification.
3. **Tier the models**: mechanical consistency (paths, versions, existence, formatting) on a cheap model; number recomputation and counter-examples on a strong one. **Never the reverse** — a cheap model checking numbers produces false green.
4. **Budget gate + circuit breaker**: ≤30M per section (tier A cumulative + one tier B); any single review >10M must be justified in the report; over budget ⇒ drop to two-stage sampling and *write "degraded sampling" in the acceptance note*.

**Expected cost for a 6-unit section**: old habit (full review each unit) ≈6 × 20M = 120M; this policy ≈5 × 2.5M + 25M ≈ **37M (−70%)**, while closeouts still get a full pass and reversals/baseline changes still get tier C.

**Honest limits**

- Incremental review cannot see cumulative drift (ten locally-correct edits can contradict each other) ⇒ tier B must genuinely re-read everything from disk and must not read the fix log.
- Token savings never remove the "recompute 3 numbers by hand" step. That is the floor.
- Not applicable when: ① the product ships externally / is submitted ⇒ tier B plus external authority; ② the criterion just changed ⇒ tier C; ③ the first time a criterion goes live, expect a one-off expensive burst (13 rounds here) — that is a setup cost, not a routine.
- Multi-agent: ask **"can this be done by one agent sequentially?"** before asking "how many to spawn". Anthropic measured orchestrator-worker ≈+90.2% over single-agent but **15× tokens** (token use explains ~80% of variance), and only for high-value parallel work; Cognition reports that splitting loses the implicit decisions carried by actions. Pass paths, not summaries.
- Independence comes from **different evidence**, not more judges: same model + same material + more debate does not improve groundedness. The second tier-B reviewer must use a different method, not re-read the same way.
