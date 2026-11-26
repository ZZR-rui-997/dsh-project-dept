# project-dept

> A generic "department" protocol: treat one complex piece of work as an **acceptable package**, run it serially, and make the deliverable trustworthy through a pre-start gate, three-level acceptance with independent review, baseline self-audit, and a direction pre-mortem.

## What it solves

When several agents (or several people) collaborate, **scheduling** is the host's job and
**judging correctness** belongs to nobody. The result: work gets produced, looks plausible,
the report says it ran — and nobody can show that it is right. Worse, it is *uniformly* wrong,
because everyone checks against the same unverified ruler.

This skill does one thing: make "correct" a decidable process with checkpoints. It does **not**
supply domain knowledge or tool operation — those belong to the project's own role cards and to
specialised skills.

## Three non-negotiables

1. **Delivered is not done.** The executor never marks its own work complete; delivery passes
   L1 self-check → L2 independent review → L3 final verdict.
2. **Independence is a hard requirement, not a courtesy.** The reviewer is not the author, did
   not take part in producing the artefact, and does not see the author's conclusion summary.
3. **The ruler is also a suspect.** Anything used as a baseline carries a provenance class; an
   internal summary may never serve as an acceptance baseline.

## When to load

- the user asks to "run this as a department / open a package / put a team on it";
- the task is large enough to split across people or rounds and the deliverable must survive scrutiny;
- the user stresses that checking must be independent;
- you are setting up or auditing a project ledger (board / register / baseline list).

## When not to load

- single-file tweaks, plain lookups, typo fixes;
- exploratory conversation with no decidable acceptance standard;
- cases that need to **intercept** tool calls in real time (use the host's hook/plugin mechanism).

## Layout

```text
SKILL.md                     routing: when to use + five-step protocol + boundaries
manifest.yaml                axes (deliverable / rigor) + conditional loading + quality_tools (the script list)
static/core/
  principles.md              non-negotiable stance + provenance classes [Origin]/[External]/[Own]/[None]
  workflow.md                run flow: Step 0 gate + Steps 1-6 (including exit codes)
  output-contract.md         artefact name + required sections + blocking conditions
static/fragments/
  deliverable/{document,code,data,model}.md    loaded by delivery type
  rigor/{exploratory,standard,critical}.md     loaded by "what happens if this is wrong"
references/                  on-demand depth (baseline / blind review / self-skepticism / mechanism choice / anti-patterns / scaffolding)
scripts/
  dept_gate.py               pre-start gate (reads dept.config.json)
  check_doc.py               mechanical assertions for documents (eight checks)
  check_skill.py             package self-lint (8 checks: frontmatter / versions / declared assets / forbidden names / budget / evals / completeness / manifest syntax incl. duplicate keys)
  run_evals.py               eval runner (static schema check; judge builds blind-judge briefs; tally for paired stats; grade deprecated)
  check_review_form.py       review-form linter (7 rules: snapshots / verdict / must-fix consistency / independence / evidence / banned phrases / a real problem)
  init_project.py            one-command scaffolding for a new project (dept.config.json + `_team/` ledger; gate exits 0 with --open-package, otherwise 2 with D0 pending)
```

## Quality tools (the authoritative list is `quality_tools` in `manifest.yaml` - do not count them here)

**`dept_gate.py`** — run before opening a package and before every report to the user. Checks
ledger structure, the current package, undisposed debts, stray scratch scripts, role cards,
untraced baselines, and whether the direction pre-mortem is still a template.

Exit codes: `0` pass / `1` blocked (structural) / `2` needs a decision (open debts) / `3` not executed —
four causes: config file not found / config unparseable (bad JSON) / **config's top level is not a JSON
object** / this directory has its own ledger dir but the config was found only in an ancestor project
(auditing the ancestor's ledger would skip this project's own debts, so the gate refuses).

**`check_doc.py`** — run before handing over a document. Eight assertions: figure / table /
equation numbering contiguity, caption↔body bidirectional for figures and tables, references,
section numbering contiguity (Word heading styles only), and terminology (the banned-term list
comes from the project config).

**Scope of the reference assertion:** the numbered style (`[1]`) is checked **both ways**; the
author-year style only checks "every listed entry is cited somewhere in the body" — the reverse
direction (a citation to something not in the list) cannot be detected mechanically, and the report
says so explicitly. Do not read it as bidirectional.

Exit codes: `0` = every **executed** assertion passed (unexecuted ones are listed — not the same as
"everything was checked") / `1` some FAIL / `2` not executed — main causes (not exhaustive): missing file;
python-docx missing; config missing / unparseable / **top level not a JSON object**; fewer than 3
structural assertions executed; **this directory has a ledger but the config was only found in an
ancestor**. (Same list as the Chinese README; the gate's not-executed code is `3`, the checker has no `3`.)
Two cases are **FAIL, not "not executed"**: (a) **when `--chapter` is not given**, the body contains
figure/table numbers but none is recognised; (b) **dangling citations**, judged "whole document first,
then this chapter": ① if the document has no captions at all while the body cites figures ⇒ FAIL
(regardless of `--chapter`); ② **cross-chapter dangling** — the body cites a number that has no caption
anywhere ⇒ FAIL. The comparison uses **(chapter, number) pairs**, so citing 图 9-9 from chapter 3 is not
satisfied by a 图 2-9 caption; a citation without a chapter number (图 9) is satisfied by a caption with
that number in *any* chapter (**note**: in a document that otherwise uses chapter-numbered figures,
a bare number is reported by A1 as a *mixed numbering style* → FAIL; unify to one style — this is a
deliberate conservative judgement, not a miss); ③ with `--chapter N`, a chapter that has **no captions of its own** and only
cites **another chapter's** figures is reported as *not executed*, with the note that those numbers belong
to other chapters (it is neither FAIL — other chapters do have captions, so nothing dangles — nor "no
citations at all"); ④ a second **not-executed** path (parallel to ③, not the only one): this chapter has no captions
and the body cites no figures at all ⇒ *not executed*.

**`check_skill.py`** — run after editing this skill package itself. Eight static checks: frontmatter
(`name` must equal the directory name, `description` <= 1024), version consistency across four places
(SKILL / manifest / README / README_EN), every asset declared in manifest/SKILL really exists (including
script paths written without an extension), no entry or in-package document may mention non-distributed
filenames, context budget (`SKILL.md` over **3,000 tokens ⇒ defect, exit 1**; `SKILL.md + always_load`
over 9,000 only warns; **actual per-run load** also adds the largest fragment per axis: over 14,000 ⇒
defect, over 9,000 warns), `evals.json` readability, package completeness, and `manifest.yaml`
syntax (parsed with PyYAML when available — a broken manifest used to ship because the self-lint only
regex-scanned it; without PyYAML a conservative heuristic flags plain-scalar continuations).

```bash
python scripts/check_skill.py --root .        # add --json for machine-readable output
```

Exit codes: `0` clean / `1` defects / `2` not executed. **The budget numbers drift with the body** —
take them from its output instead of copying a constant from the docs.

**`run_evals.py`** — run when routing or review behaviour changes, and for A/B validity checks:

- `static`: validate the `evals/evals.json` schema and print a ready-to-paste grading brief per case;
- `judge --answers <dir> --out <dir> [--seed 7]`: anonymise `<case>-<arm>-r<rep>.txt` answers into a
  blind-judge sheet (A/B/C… shuffled, private arm map) plus a paste-ready score template;
- `tally --out <judge-out-dir>`: paired statistics, per-rubric breakdown, Wilson 95% interval;
- `grade`: **deprecated** — verbatim keyword grading produced 12/12 false FAILs on 12 real answers
  (backlog P-15-8), so it must not be used as an acceptance criterion; `compare` is built on `grade`
  and is a direction hint only.

```bash
python scripts/run_evals.py --mode static
python scripts/run_evals.py --mode judge --answers path/to/answers --out path/to/judge-out
python scripts/run_evals.py --mode tally --out path/to/judge-out
```

Exit codes: `static` 0 pass / 2 not run; `judge` 0 pass / 2 malformed answer directory or not run;
`tally` 0 pass / 2 not run or a template with blanks (each blank is named); `grade` 0/1/2
(deprecated, regression only).

**`check_review_form.py`** — run it on every incoming review form. Seven structural rules: two anchor
snapshots in §0 (if they differ, the form must say the verdict only covers the start version), exactly
one legal verdict in §1 (`通过` / `通过但要修` / `不通过`), verdict not contradicting must-fix rows,
independence (independent conclusion written before reading the author's self-check), a mechanical
evidence table in §1, none of 8 banned evidence phrases ("consistent with the old version", "the author
said", "looks reasonable", …), and at least one real problem.

```bash
python scripts/check_review_form.py review-form.md
```

Exit codes: `0` compliant / `1` defects / `2` unreadable.
**Limit of what it proves:** it checks **traces, not behaviour** — copying the same hash twice or listing
one trivial unrelated problem both pass. Independence and the evidence table are trace checks too: a body
sentence admitting the author's self-check was read first still passes (only the qualifier phrase is matched),
and any two evidence rows carrying a path or line number count. It does not replace the Lead actually reading
the form.

Both the documentation tools and the review-form linter use only the standard library, resolve paths
relative to themselves or to the config, and hard-code no machine paths.

## Standing it up in a project

See `references/project-scaffold.md`: create the `_team/` ledger, write `dept.config.json`,
write role cards, seed the baseline register, wire the quality tools, run a smoke package.
Moving to another machine means copying `~/.dsh/skills/`.

**One command stands a new project up** (no more copying ledgers from another project):

```bash
python scripts/init_project.py --root <project-root> --desc "<one line>"
python scripts/init_project.py --root <project-root> --open-package "package 1: <goal>"
```

It writes `dept.config.json` plus `_team/` (charter, flow, board, register, baseline list, baseline
changelog, three generic role cards, task/review templates, `bin/` note, project-level `AGENTS.md`).
It is idempotent: **existing files are never overwritten** unless `--force` is passed; also
`--dry-run`, `--json`, `--roles`. Without `--open-package` the board says "no package open yet"
and carries a single open debt `D0`, so the gate exits **2** (needs a decision) - honest: no package,
no start. With `--open-package` the gate exits 0 with zero warnings.


## Boundaries

This skill governs **process and acceptance**. It does not govern: domain conventions (which
model, which parameters) — role cards and discipline skills; tool operation — dedicated skills;
desktop interaction — desktop-control skills; real-time interception — host plugins.

## Honest limitation

Independent review can check whether a number is right. It **cannot** check whether a model
should have been built this way. Errors at the method level pass review. That is why the
`critical` tier additionally requires a written direction pre-mortem, full baseline
re-verification, and a named human signature — and never allows substituting your own approval
for someone else's.

## Panel review

A single reviewer is the default. Escalate to a **panel** (2–3 reviewers) on triggers, not
routinely (cost ≈ N× one review): the artefact will become a baseline other work checks against /
a prior review on this subject **missed something material** / the user asks for it / the
Lead-controlled weaknesses (package assembly, brief, sampling) cannot otherwise be mitigated
for this package.

Composition: reviewers must use **different anchor methods** (one recomputes, one checks against
external authority, one works internal consistency) — a panel that shares one method shares one
blind spot; optionally designate a **devil's advocate** whose brief is to attack the conclusion;
reviewers write independent conclusions with **no cross-visibility** and **no shared inputs**;
record the roster in the board. Verdict: any single real problem blocks; unanimous PASS still
requires the Lead's L3 probe (and human sign-off for critical).

See `references/blind-review.md` § Panel review.

## Changelog

### 1.3.10 (2026-11-26: the mandatory fixes from the v1.3.9 tier-A blind audit)

**Why**: v1.3.9 passed the tier-A incremental audit (12/12 scenarios, 3/3 mutations caught, 184 tests), but the
auditor found two claim-vs-reality mismatches and two suggestions - all text and edge cases, no mechanism change.

1. **P1 (important)**: the structure tree said `init_project.py` "gate passes right after"; in reality the default
   run leaves one open debt `D0`, so the gate exits **2** - only `--open-package` gives exit 0. Text corrected.
2. **P2**: the generated `dept.config.json` hard-coded this machine's venv path in `environment.notes`, directly
   contradicting "generic hints only / never hardcode local paths" (and there was no way to override it). Now three
   generic notes, plus a repeatable `--env-note TEXT` for project-specific entries.
3. **P3**: `references/project-scaffold.md` allowed copying the quality scripts into a project `bin/`, which
   conflicted with `bin/README` ("pointer, not a copy"). Reconciled: call them from the skill by default; copying is
   allowed only as an **unmodified snapshot** for offline reproducibility, with its sha256 recorded and re-synced
   when the skill version changes.
4. **P4**: the 1.3.9 entry omitted `基准清单.md` from the ledger list; added.
5. Version -> **1.3.10**; tests **184 -> 186** (default notes contain no machine path; `--env-note` lands in config).
   Mutation: putting the hard-coded path back makes the new test fail.

**Honest limitations**: (1) still skeletons - domain role cards must be rewritten; (2) `--env-note` appends without
deduplicating, so passing the same text twice yields two entries; (3) token estimates still not calibrated against a
real tokenizer (see the 1.2.x entries).

### 1.3.9 (2026-11-26: scaffolding a new project is now automatic)

**Why**: the discipline worked, but moving to a new project meant hand-copying the ledger; without
it the gate can only return `3` (not run), so "works globally" stopped at the installation layer.

1. **New `scripts/init_project.py`** (standard library only): writes `dept.config.json` + the four
   ledger files (including `基准清单.md`) + baseline changelog + generic role cards (lead/audit/reviewer) + task/review
   templates + `bin/` note + project `AGENTS.md`. Idempotent (existing files skipped unless
   `--force`), plus `--dry-run`, `--json`, `--roles`, `--open-package`.
2. **Gate agreement is a test, not a claim**: `tests/test_init_project.py` (11 cases) runs the real
   CLI and then the real `dept_gate.py`: open package => exit 0 with zero warnings; no package =>
   exit 2 naming `D0`; one open debt => exit 2 naming `D1`; re-run is idempotent; the generated
   review sheet must still be rejected by `check_review_form.py` (so the template is not vacuously valid).
3. Version -> **1.3.9**; tests **173 -> 184**.

**Honest limitations**: (1) these are skeletons - **domain role cards must be rewritten by someone who
knows the domain traps**; (2) `environment.notes` carries generic hints only; (3) no cross-window
inbox is created (single-window projects do not need one); (4) the entry-token budget is unchanged
(`init_project.py` is not in the always-load set).

### 1.3.8 (2026-11-25, one must-fix from the v1.3.7 tier-A review)

The v1.3.7 tier-A reviewer (six spellings, counter-examples for non-standard spellings, 3/3 reversion
mutations caught, 33/33 snapshot, identical `FILES 36` start/end) returned "pass with required changes"
with one real defect left.

1. **A literal pre-filter still sat in front of the regex**
   (`marked = "[已作废]" in s or "[superseded]" in low` + `if not marked: continue`). So legal spellings
   with whitespace inside the brackets — `[ 已作废 ]`, `[superseded ]`, `[　superseded　]` (ideographic
   space) — were filtered out and **exited 0 silently**, contradicting the README claim of
   "matched anywhere in the line" (the reviewer measured `RETIRED_MARK_RE.search(...) == True` while the
   pre-filter said False).
2. Fix: **delete the pre-filter**; the only entry is `if RETIRED_MARK_RE.search(s):`. The regex already
   allows inner whitespace via `\s*`; the pre-filter was a second, divergent rule — two rules for one
   thing always drift.
3. New regression test: the three inner-whitespace spellings, each with a marker and no changelog, must
   exit 1.
4. Version -> **1.3.8**; tests **172 -> 173**.

**Evidence**: `unittest` **173 OK**; `check_skill` **8/8 exit 0**; `run_evals --mode static` exit 0;
mutation: re-adding the pre-filter turns all three sub-cases red (`failures=3`).

**Honest limits**: only the two bracketed spellings are recognised (`【已作废】`/`（作废）` are not —
measured and stated); markers are hand-written; recognising a marker says nothing about the content of
the changelog.

### 1.3.7 (2026-11-25, one must-fix from the v1.3.6 tier-A review + an honest limitation)

The tier-A reviewer (14 self-written fixtures, 3/3 reversion mutations caught, 36/36 snapshot match)
returned "pass with required changes" with one real defect left.

1. **Retired markers were only recognised at line start or after a leading table pipe** (measured:
   the legal table row `B2 | 相关长度 | [已作废] |` has no leading pipe, so the gate exited 0 silently).
   Now there is a single rule: the regex `\[\s*(?:已作废|superseded)\s*\]` (case-insensitive) is
   searched **anywhere in the line** — line start, `- ` bullets, `1. ` ordered lists and any table
   cell are all recognised.
2. **Limitation rewritten honestly**: it previously listed only `【已作废】`-style spellings, while
   `- `/`> `/`1. ` forms were also missed at the time. Those three forms are now covered; the
   remaining limit is that only the two bracketed spellings are recognised (`【已作废】`, `（作废）`,
   `废弃` are still invisible).
3. Removed one **dead variable** in `tests/test_dept_gate_baseline.py` (reviewer F3).
4. Added 3 regression tests: table cell without leading pipe / `- ` bullet / `1. ` ordered list.
5. Version -> **1.3.7**; tests **169 -> 172**.

**Evidence**: `unittest` **172 OK**; `check_skill` **8/8 exit 0**; `run_evals --mode static` exit 0;
mutation: reverting to `startswith` turns the no-leading-pipe table test red (exactly the reviewer's case).

**Honest limits**: only two bracketed spellings; markers are hand-written (a misspelling or a marker
wrapped in Chinese quotes escapes); recognising a marker says nothing about whether the changelog
content is correct.

### 1.3.6 (2026-11-25, three must-fix items from the v1.3.5 tier-B review + one written claim)

Both tier-B reviewers (different methods, mutually blind, 33/33 snapshot match) returned
"pass with required changes". Fixing those four items is v1.3.6.

1. Check 7b used an **undeclared ">= 40 chars" threshold instead of "non-empty"** (reviewer measured:
   a complete 38-character record was rejected with a misleading "missing or empty"). Now the rule is
   explicit: the changelog exists and contains at least one non-empty, non-heading line. No length
   threshold anywhere.
2. **Case-sensitive line-start markers** (`[Superseded]` slipped through with exit 0, while the table
   path was case-insensitive) — both paths now compare on `lower()`.
3. **A retired row with no `baseline_changelog` key only warned** (P-15-9 was bypassable) — now a
   structural block (exit 1) telling the project to add the key first.
4. The README claim "`must_include` unchanged" could not be checked from the package — rewritten to
   say the author-side diff against the v1.3.4 blind-review package's `evals.json` showed 7/7
   identical fields, **and that the baseline is not distributed, so the claim cannot be re-checked
   externally**.
5. Version -> **1.3.6**; tests 166 -> **169** (short complete record passes / uppercase marker blocked
   / retired row without config key blocked).

**Evidence**: `unittest` 169 OK; `check_skill` 8/8 exit 0; `run_evals --mode static` exit 0;
3/3 mutations caught (revert to `len < 40` -> short-record test red; restore case sensitivity ->
uppercase test red; revert to warning-only -> missing-key test red).

**Honest limits**: (a) "has a record" only proves the file has body text, not that the old/new values
or `superseded_by` are right; (b) only the two bracketed spellings are recognised, so `【已作废】` or `（作废）` still escape; (c) item 4 fixes the *checkability of a claim*, not the claim itself —
"7/7 identical" still rests on author-side evidence only.

### 1.3.5 (2026-11-25, P-15-9: attach the rule to a mandatory artefact + eval-owned rubric)

**Why**: in the v1.3.0 A/B (n=15, with 81.7% vs without 47.5%) one item stood out — on
`baseline-is-wrong`, the "mark superseded, never delete the old row" rubric item scored **4/20**
across both arms (the arm holding the full text still only 2/10), while the two items that have a
concrete artefact (review form, final-verification record) scored **10/10** on the same arm.
Lesson: **a rule that lives only in a reference page, with no artefact attached, does not get
executed.**

1. `static/core/output-contract.md`: new hard rule — when a baseline / metric / definition is
   retired or replaced, the delivered package must carry a **baseline changelog table** (old value,
   new value or reason, `superseded_by`, which downstream results were re-run and which were not);
   otherwise it is a blocker. The rule is attached to the deliverable, not to a reference.
2. `scripts/dept_gate.py`: new check 7b — if the baseline list carries `[已作废]` / `[superseded]`
   rows, the file named by `dept.config.json` → `baseline_changelog` must exist and be non-empty,
   otherwise the gate is structurally blocked (exit 1); with no retired rows the file is not
   required and nothing is falsely flagged. New config key `baseline_changelog`.
3. `static/core/workflow.md` Step 6: close-out must reconcile the baseline changelog.
4. `evals/evals.json`: every one of the 7 cases now carries `rubric` (4 semantic items).
   `build_rubric()` already preferred an explicit rubric; the data simply never had one.
   On the author side the old and new `evals.json` were diffed field by field against the
   v1.3.4 blind-review package: `prompt` / `expected_output` / `budget_hint` / `must_include` /
   `must_exclude` / `axes` / `steps` are identical for 7/7 cases. **That baseline is not
   distributed with this package, so the claim cannot be re-checked from the package alone.**
5. `scripts/run_evals.py`: static validation for `rubric` — exactly 4 items, non-empty, >= 8 chars,
   and **not copied verbatim from `expected_output`**.
6. Project side: the review-form template gains a per-artefact sha256 section; the project baseline
   list gains the retirement notation; a baseline changelog file was created with 8 back-filled
   historical retirements.

**Evidence**: `unittest` 166 OK; `check_skill` 8/8 exit 0; `run_evals --mode static` exit 0;
3/3 mutations caught (disabling 7b turns 3 tests red; removing rubric validation turns 2 red;
ignoring the explicit rubric turns 1 red).

**Honest limits**: (a) 7b only proves the changelog file exists and is non-empty, not that its
values are right; (b) the retirement marker is hand-written, so a typo escapes detection;
(c) rubrics are author-written and their portability across models/judges is untested
(P-15-11 / P-15-12 remain backlog); (d) the 8 back-filled entries are a reconstruction, and several
"downstream not re-run" rows are genuine debt rather than completed work.

### 1.3.4 (2026-11-25: one must-fix from the tier-A audit, same rule again)

The tier-A audit of v1.3.3 was "pass with must-fix": A1-A5 all held (six fixture verdicts correct, three mutations
reddening 1/2/1 tests, 157 tests green, 8/8 self-checks exit 0, versions aligned, snapshot 32/32, and all four
README self-claims verified). Only one item remained: **stacked markers defeat the hint detection**.

1. **Must-fix (a new false pass)**: `> **hint**: ...`, `>**hint**`, `( **hint** )`, `> - **hint**`, `> **note**`
   all exited 0 in v1.3.3 (they exited 1 under v1.3.2), because v1.3.3 stripped only one layer of markers. Now
   `_strip_lead_markers()` loops until stable (quote marker, parentheses, list markers, emphasis, quotes).

Unit tests **157 -> 159**, adding two **table-driven** cases: `test_hint_forms_are_not_independence` (10 template
trace spellings including the stacked forms) and `test_legit_forms_are_independence` (5 legitimate spellings including
`> I wrote ...`, `> **I wrote ...**`, `- **independence**: ...`). Table-driving is the deliberate fix for the pattern of
the previous two rounds (patch one case, get broken by another spelling next round).
Mutation: reverting the loop to a single strip reddens `test_hint_forms_are_not_independence`.

### 1.3.3 (2026-11-25: one must-fix plus one leftover suggestion from the tier-A audit, same rule)

The tier-A audit of v1.3.2 was "pass with must-fix": A1-A5 all held under independent fixtures (three legitimate
declaration styles exited 0, three template traces exited 1, the reported line was body line 27 rather than the
heading, three revert mutations each turned a test red, 154 tests / 8 self-checks / versions aligned / snapshot 32/32).
Only one minor must-fix and one suggestion remained.

1. **Must-fix (false defect)**: treating every line starting with `>` / `(` / the fullwidth `（` as a template trace was
   too broad - a legitimate declaration written as `> I wrote the conclusion first ...` or `- (1) I ...` was dropped
   and then reported as a defect. Now the marker is stripped first and only a line that **then starts with a hint word**
   counts as a template trace.
2. **Leftover suggestion**: the hint list lacked the word for "hint/tip", so a skeleton line like `- Tip: write the
   conclusion before opening the self-check` passed as evidence. Added.

Unit tests **154 -> 157**, with 3 new regressions (parenthesised declaration, blockquote declaration, bullet hint label),
plus 3 revert mutations: M1 (unconditional skip for `>`/`(` lines) reddens the blockquote case; M2 (drop the hint word)
reddens both hint-line cases; M3 (report the first line containing "self-check") reddens the line-number case.

**Honest note**: M1 only reddens 1 of the 3 new cases - the `- (1) I ...` case goes through the bullet branch and never
reaches that rule. So the new cases do **not** discriminate uniformly; recorded here so that "some mutations went red"
is not mistaken for "all mutations went red".

### 1.3.2 (2026-11-25: two must-fix items from the tier-A audit, both in the independence rule of `check_review_form.py`)

The tier-A audit of v1.3.1 was "pass with must-fix" (all 10 required checks met, 4 revert mutations each turned the
corresponding test red); only two minor items remained, both introduced by my own previous patch.

1. **False defect**: the skip-hint rule applied to *any* body line, so a legitimate independence statement that merely
   mentioned a word like "requirement" or "note" was skipped as a template line and then reported as missing its
   qualifier. Now template traces are recognised **only by line-start shape** (headings, `>` quotes, parenthesised
   hints, lines starting with a hint word; bullet markers are stripped first), so words in mid-sentence do not matter.
2. **Wrong line reported**: on failure the checker quoted the first line containing the word "self-check", which could
   be the skipped heading. It now reports the **first real body candidate**, falling back only if there is none.

Unit tests **150 -> 154**, with 4 new regressions (a sentence that contains a hint word must pass; a template label
line must not count; a blockquote hint line must not count; the reported line number must point at the body line,
not the heading), plus 3 revert mutations to prove each fix is load-bearing.

### 1.3.1 (2026-11-25: five must-fix items from the tier-B panel - all documentation-level)

**Context**: in the v1.3.0 tier-B panel the declaration-consistency reviewer (`verify-c2-decl130`) returned
**not passed**: behaviour and regressions were fine (8/8 self-lint, 146 unit tests, 32/32 snapshot match), and
every problem was documentation claiming something the artefact does not do - this package's oldest failure mode.

1. `README_EN.md`'s `check_skill.py` section still said "Seven static checks" and omitted check #8 => now "eight"
   plus the manifest-syntax item.
2. Neither language documented exit codes for `run_evals.py`, while the changelog claimed all five scripts had
   runnable usage and exit codes => exit codes added for all four modes.
3. The **1.1.0** entry in `README_EN.md` said "eight static checks" (it was seven then) => corrected to
   "seven ... (an eighth came in 1.3.0)"; historical entries must keep history.
4. `references/project-scaffold.md` still recommended `grade`/`compare` => now recommends `static`/`judge`/`tally`
   and states that `grade` is deprecated and must not be an acceptance criterion.
5. The docstrings of `check_skill.py` and `tests/test_check_skill.py` still said "7 checks" => 8.

6. The behavioural reviewer in the same panel (`verify-c1-behavior`, verdict "pass with must-fix") found three
   rules that **claimed more than they enforced**; all three are tightened, each with a regression test:
   (a) `check_review_form.py` independence no longer accepts **template headings** ("written before opening the
   author's self-check" ships in the template itself, so it passed for free); (b) the mechanical-evidence rule now
   requires **at least 2** real rows in the "recompute / rerun / recheck" table (placeholder rows containing `<`
   and rows from the problem table do not count); (c) `check_skill.py` check #8 now flags **duplicate top-level
   keys** (PyYAML silently lets the later one win).
7. `run_evals.py --mode tally` now **scans every case before reporting blanks**: the old code raised on the first
   case, so blanks in later cases were never named. Unit tests **146 -> 150**, with 4 mutations proving each fix
   fails when reverted.

**Why a separate version for prose**: none of the five changes behaviour, but a wrong claim in the protocol layer
makes humans and agents follow the wrong rule - and "declaration vs artefact mismatch" is the single most
repeated failure across this package's thirteen review rounds, so prose gets fixed, versioned and re-reviewed.

**Honest notes**: the reviewer also flagged that this round's blind package `验收标准.md` said "30 files" while the
snapshot has 32 (author typo, not a package defect); and recorded that the "proves traces, not behaviour" caveat on
`check_review_form.py` is **honest** - using its own self-declared cheat (copy the same hash twice plus one typo)
produced a form that passes, i.e. the hole is reproducible rather than hidden.

### 1.3.0 (2026-11-25: three new mechanical checks + one effectiveness experiment)

**New or changed behaviour**

1. **`scripts/check_review_form.py` (new, P-15-4)** — review forms stop being free text: 7 structural
   rules (§0 two anchor snapshots, one legal verdict in §1, verdict not contradicting must-fix rows,
   independence written before reading the author's self-check, a mechanical evidence table in §1,
   8 banned evidence phrases, at least one real problem), 23 tests, and 8 mutation runs that each flip
   the corresponding rule and make its test fail. **Why**: the anchor hash was in the template but nobody
   checked it — and it proves *traces*, not *behaviour*, which is now stated in the README too.
2. **`run_evals.py` gains `judge` / `tally`; `grade` is DEPRECATED (P-15-8)** — verbatim keyword scoring
   produced **12/12 false FAILs** on 12 real answers (the two arms were indistinguishable). `judge`
   anonymises `<case>-<arm>-r<rep>.txt` answers into a blind-judge sheet (random A/B/C… labels, private
   arm map, paste-ready template); `tally` reports paired wins, per-rubric breakdown and a Wilson 95%
   interval. **Why**: the old judge rewarded copying words out of `expected_output` and rejected correct
   answers phrased differently — the "a weak judge can fail correct responses wholesale" failure mode.
3. **`check_skill.py` no longer silently skips non-UTF-8 documents (P-15-5)** — a read failure is now a
   **defect** (GBK / UTF-16 `.md` files used to escape the stale-wording and forbidden-name scans).
   3 regression tests plus mutation proof.
4. **Docs (P-15-6 / P-15-7)** — the quality-tools section now documents all five scripts with runnable
   commands and exit codes; prose no longer contains a bare decode literal that grep confuses with a
   command example.
5. **`check_skill.py` check #8, "manifest syntax" (P-15-10)** — this package's own `manifest.yaml` had
   been **invalid YAML since v1.2.x** (`skill_lint_output` was a plain scalar whose continuation line
   carried a `key: value`-shaped note), and the self-lint only regex-scanned the manifest, so it
   **never parsed it**; the defect shipped across several version numbers. Check #8 now runs
   `yaml.safe_load` when PyYAML is available and reports the parser's own message; without PyYAML it
   degrades to a conservative heuristic (parent is a plain scalar while a deeper line looks like
   `key: value`). Both paths have regression tests and a mutation self-proof.
   **Why**: this is the second time we wrote broken YAML, and the previous time was also caught only by
   an external reviewer — a tool that does not parse cannot be said to check.

**Evidence, not promises**

- **P-15-2 expanded to n=15** (3 cases × 2 arms × 5 reps × 2 blind judges): with **98/120 = 81.7%** vs
  without **57/120 = 47.5%**, **+34.2 pp**, paired **11 wins / 4 ties / 0 losses**, Wilson 95%
  **CI [48%, 89%]**. **Read together with**: the same rubric at n=6 gave **+60.4 pp** back then ⇒
  **small samples overestimate**; both numbers are reported.
- Gains concentrate in **structural** items (L2 reviewer must not be the author 10 vs 5; Lead re-checks at
  L3 10 vs 6; mechanism-choice R2/R3 9–10 vs 0), while items the base model already handles ("do not
  self-mark complete") are 10/10 in both arms.
- **Newly exposed weakness (backlog P-15-9)**: for `baseline-is-wrong`, R3 (stop downstream + file a debt)
  totals 6/20 across arms and R4 (mark superseded, never delete) totals **4/20**; the with-arm still only
  scores 2/10 with the whole skill loaded ⇒ **rules that live only in `references/` and hang on no mandatory
  artefact are not reliably executed by an agent**.

**Honest limitations (not solved in this version)**

- `grade` is only marked deprecated; the code is still there, and `compare` still builds on it (direction
  hint only).
- The 7 cases in `evals/evals.json` **still have no `rubric` field**, so `judge` derives points from
  `must_include` and the rubric stays keyword-ish; encoding the four semantic criteria from P-15-2 into
  `evals.json` is what would make it real.
- `judge` has no fill-in wizard (judges edit the template), and `tally` stops at a Wilson interval
  (no McNemar / bootstrap / multiple-comparison correction).
- Token estimation is still not calibrated against a real tokenizer (no tiktoken/transformers on this machine).
- All of the above is **author-side self-testing plus one expanded experiment**; v1.3.0 has not been
  independently reviewed yet.

### 1.2.2 (2026-11-25: the 3 must-fix items from the tier-A incremental review)

The tier-A review of v1.2.1 returned "fail", with 3 must-fix items - all of the same class: a rule or a claim that
only holds in one place.

1. **A rule that only covered the three entry docs**: the stale-count check scanned `README.md` / `README_EN.md` /
   `SKILL.md` only, so the same old wording in `references/project-scaffold.md:85` escaped it and the real package
   still exited 0. A rule that is not "everywhere" is worth nothing => it now scans **every `.md` in the package**,
   plus a test that plants the old wording under `references/` and requires it to be caught. That scaffolding section
   now says "wire every script listed in `quality_tools`" (gate / checker / self-lint / eval runner).
2. **The structure tree listed only 2 scripts**: `scripts/` trees now include `check_skill.py` and `run_evals.py`.
3. **Token numbers had two bases (off by 1)**: the documented command used `encoding='utf-8'` while
   `check_skill.read_text()` uses `utf-8-sig`; the BOM made them differ (1732 vs 1731). The command now says
    `utf-8-sig`; the numbers measured then were **1,731** / per-run **6,041** (**they drift as the text
    changes - always take them from `check_skill.py`**, never copy them from here).

**Process defect (recorded honestly)**: the author edited the package **during** this review (fixing the reproducible
numbers and rebuilding the snapshot), and the reviewer called it out. Lesson: once a package is frozen for review it
must not be touched; change it and you void the round, rebuild the package and re-review. This is now a rule.

### 1.2.1 (2026-11-25: the 4 must-fix items from the tier-B panel - each turned into a machine check)

The v1.2.0 tier-B panel (two reviewers, different methods) both returned "pass but must fix": 4 must-fix + 2 observations.
This release does not just reword the docs:

1. **Stale count (R1-F1)**: README still carried a stale count (implying only 2 tools) while `scripts/` has 4. Docs now
   point at `manifest.yaml`'s `quality_tools` instead of counting, and a lint check flags the old "only two of them" wording
   whenever the declared script count is not 2. That check is a **literal** scan, so the docs must not contain those phrases
   either - including when explaining the rule (paraphrase if you need to refer to it).
2. **Unreproducible token numbers (R1-F2 / R2-1)**: "4,563 -> 1,600-1,700" replaced by the package estimator's reproducible
   **4,935 -> 1,718** (the value right after the v1.2.0 trim; **1,731 measured at the time** after the v1.2.2 wording tweaks - it drifts with the text and version string, so always take the current value from `check_skill.py`), with the
   command to reproduce it.
3. **Budget limit was dodgeable (R2-2)**: `CJK_RANGES` missed kana (0x3040-30FF), hangul (0xAC00-D7A3), emoji
   (0x1F300-1FAFF) and extension B (0x20000-2A6DF); padding with those was estimated at 3.5 chars/token and slipped under 3,000.
4. **Fragments were outside the budget (R2-3)**: it only counted `SKILL.md + always_load`. Now a "per-run actual load"
   includes the largest fragment per axis: warn 9,000 / hard defect 14,000 (v1.2.2 measurement: 6,041; +595 deliverable / +754 rigor - **take the number from `check_skill.py` output**, it drifts with the body).
   A missing fragment is a defect too.
5. **Extension-less declarations escaped validation (R2-4)**: a declaration like `scripts/check_skill` was never checked,
   contradicting the manifest's "declared missing = DEFECT". `always_load` and `quality_tools` are now resolved against the tree.
6. **Two wording/naming inconsistencies (observations)**: "the changelog exists only once" while two language copies were
   listed; and "six-step" while the flow actually has Step 0-6. Both aligned.
7. **Tests**: 4 new regression tests (CJK ranges, fragment bloat, extension-less declarations, stale counts) - and, per our
   freeze rule, reverting any of these fixes must make them fail.

**Honest limits**: see 1.2.0 - still an estimate, never compared with a real tokenizer.

### 1.2.0 (2026-11-25: entry body cut to ~1/3; the context budget becomes a hard limit)

**Why**: `SKILL.md` is the fully-loaded entry point, and its body had grown to ~**4,935 tokens** (the package's own `estimate_tokens()`; the hard limit back then was 5,000) -
of which ~**2.9K tokens were a changelog table duplicated line-for-line from `README.md`**.
Keeping one history in two places guarantees drift (this is exactly our own "a second copy rots" anti-pattern),
and it crowds out the context budget available for real work: 64% of the entry budget was history.

**What changed**:
1. **The changelog table is gone from `SKILL.md`**; only a short "where the changelog lives" section remains
   (pointing at README / README_EN) plus one hard rule: do not write change details back into the entry body.
   History is not an execution input; the entry keeps routing and non-negotiables only.
   **Measured (v1.2.0, at the time)**: `SKILL.md` 4,935 -> **1,718 tokens** (same `estimate_tokens()` basis;
   after the v1.2.2 tweaks it measured **1,731**; the current value always comes from the command). Reproduce with
   `python -c "import sys;sys.path.insert(0,'scripts');import check_skill as c;print(c.estimate_tokens(open('SKILL.md',encoding='utf-8-sig').read()))"` -
   **use `utf-8-sig`**, the same basis as `check_skill.read_text()`; with plain `utf-8` the BOM makes it differ by 1),
   `SKILL.md + always_load` ~**4,664 tokens**.
2. **The context budget is now a hard check**: in `check_skill.py`, `SKILL.md` over **3,000 tokens** is a **defect (exit 1)**,
   no longer a `[!]` warning; `SKILL.md + always_load <= 9,000` stays a warning (it varies with project-side always_load,
   so it is unsuitable as a hard gate). The error text says what to do: "sink details into references/ or README.md".
3. Tests updated: the old "over budget only warns, exit 0" case became "**over the hard limit => exit 1**",
   plus assertions that `--json` reports `budget.skill_md_limit == 3000` and `ok == false`.

**Honest limits**:
- Tokens are still **estimated** (CJK char ~1 token, otherwise 3.5 chars/token; since 1.2.1 the CJK ranges also
  cover kana / hangul / emoji / extension-B, which previously could be used to dodge the limit). It has **not** been
  compared against a real tokenizer (no tiktoken/transformers on this machine), so it is only comparable within itself;
  the 3,000 line is defined in that estimator, so the headroom shifts with a real tokenizer.
- An agent that reads only `SKILL.md` no longer sees version history - a **deliberate** trade-off: history does not
  drive execution, and README is reachable inside the same package (not a dead reference).
- The hard limit turns "I want to add one more paragraph to the entry" into exit 1; the mitigation is to put it in
  `references/` and leave a one-line pointer. That is the design intent, not a bug.

### 1.1.1 (2026-11-25: two must-fix items from the tier-A review, plus two untrue self-descriptions)

The 1.1.0 snapshot was handed to one independent reviewer under the **tier-A incremental review** and was **rejected** (4 must-fix items). All four are fixed here; **no scoring rule changed** - only the output contract and the prose:

1. **`check_skill.py` gains `--allow-dirname-mismatch`** - "frontmatter `name` must equal the directory name" is a hard Agent Skills requirement, but it misfires whenever the package is copied elsewhere (e.g. a review bundle named `skill\`). It stays a **defect by default** (the shipped package must match); the flag downgrades it to a warning. **Why**: a reviewer running the baseline against a renamed copy got exit 1 with zero real defects.
2. **`dept_gate.py --json` now emits pure JSON** - it used to print the `[anchor]` line, a separator and the human verdict as well, so only the last line parsed. **Why**: if a machine interface says "JSON only", it must be JSON only.
3. **Duplicate top-level headings merged** in both READMEs (`## 变更记录` / `## Changelog` each appeared twice) - an artefact of inserting the 1.1.0 block.
4. **Documented that the budget check only warns** - the 1.1.0 entry described the check but not that exceeding it still exits 0 (measured behaviour: warning + exit 0).

**Honest limits**: `--allow-dirname-mismatch` could be abused as a permanent "skip the name check" switch; mitigation is that it downgrades only that one item and leaves a visible `[!]` trail. The other four limits are as in 1.1.0.

### 1.1.0 (2026-11-25: four mechanism gaps closed; machine self-check for "claims vs artefacts")

Based on a survey of comparable projects (DSH plugin market, Claude ecosystem, Agent Skills spec, and counter-evidence on multi-agent systems), only gaps that map to a **real incident** were closed. No new roles, no fourth log:

1. **`scripts/check_skill.py` (new)** - seven static checks at that time (an eighth, manifest syntax,
   came in 1.3.0): frontmatter (`name` must equal the directory name, `description` <= 1024), **version consistency across four places** (SKILL / manifest / README / README_EN), every asset declared in manifest/SKILL actually exists, entry documents must not mention non-distributed filenames (author-side verification record, fix-progress log, project board, delivery register), context budget (SKILL body <= 5000 tokens, SKILL + always_load <= 9000; **over-budget only warns, never blocks - exit stays 0**), `evals.json` readability, package completeness. **Why**: the same dead reference shipped twice, the version drifted three times, and one declared asset did not exist - all mechanical checks that human eyes miss.
2. **Snapshot anchor** - `dept_gate.py` now prints an `[anchor]` line and accepts `--json`; the value is the first 12 hex chars of sha256 over the config plus the four ledgers. The review template gains a "snapshot anchor (recorded before and after the review)" field. **Why**: during round 5 a reviewer's package was edited mid-review; with an anchor that is caught on the spot.
3. **`evals/` turned from dead data into runnable checks** - each case gains `assertions{must_include, must_exclude, axes, steps}`; `scripts/run_evals.py` provides `static` (schema + judge prompt), `grade` (deterministic assertion scoring) and `compare` (with-vs-without directories, with a small-N warning). **Why**: the author-side verification record admitted "7 static cases, no runner" - i.e. no eval at all.
4. **Two new procedures** (project-side `_team\工作流.md` sections 4.13 / 4.14) - **pre-execution plan review** (when rigor=critical, planned machine time > 8 h, or the user asks; one read-only reviewer covers method, evidence/acceptance and downstream blast radius, then returns go / no-go / go-after-fixes, <= 3M tokens) and the **twice rule** (after two consecutive failures of the same approach, switch path and say why; never resend a third time).

**Deliberately not adopted** (rejected via the three optimisation questions): append-only event log, capability/bandit routing, 12-role pipeline, full panel for every task, "more homogeneous judges = more reliable".

**Honest limits**: token budget is an estimate (+-10-15% vs a real tokenizer); version detection takes the highest semver in each README (heuristic); keyword scoring cannot judge paraphrases and misfires when a forbidden phrase appears inside a negation; `compare` is directional (N=7, single grading), **not** an equivalence proof; an anchor proves files did not change, not that the change was right.

### 1.0.14 (2026-11-22, tests only, no runtime change)
A **coverage hole** found after the freeze — by the author's own mutation testing, not by a reviewer:

- the round-10 fix for the mixed-key sort crash (`--chapter` with both chapter-numbered and bare-numbered
  references made `sorted()` compare `None` with `str`) was **not actually covered** by the
  `test_mixed_keys_do_not_crash` case added in v1.0.11: both keys in that fixture happened to be satisfied,
  so `missing` was empty and nothing was ever compared. Reverting the fix left all 49 tests green.
- added `test_mixed_keys_missing_set_does_not_crash`, which builds a non-empty `missing` containing both a
  bare number and a chapter-numbered one; reverting the fix now makes that test fail (verified by mutation).
- **no runtime behaviour changed** (test only), but the version is bumped so the snapshot stays referenceable.
### 1.0.13 (2026-11-22)
Follow-up after the twelfth round returned "fail" (all three were wording / test-strength issues, no
behavioural defect):

- the Chinese README's exit-2 list was still an exhaustive five-item list while the English one said
  "main causes (not exhaustive)" and both claimed to be the same table ⇒ the Chinese list now says
  "main causes, **not exhaustive**" and mentions the extra paths the code has (empty document, too few
  structural assertions).
- the new unit test had **no discriminating power**: reverting the defect left it green, because the old
  message was "chapter 2, [7]" (bracketed) while the assertion only checked that "图 7" was absent. It now
  also asserts `[7]` is absent, and this was verified by mutation (the test fails on the reverted copy).
- `SKILL.md`'s 1.0.11 row no longer contains the bare-number note that belongs to 1.0.12.
- `README_EN` "one documentation gap" → two (the Chinese README already said two).

### 1.0.12 (2026-11-22)
Follow-up fixes after the eleventh round returned "pass with fixes" (no blockers):

- **bare citing numbers are no longer reported under the current chapter**: a citation `图 7` that belongs
  to chapter 3's `图 3-7` used to appear in A4 as "chapter 2, [7]" when checking chapter 2; a bare number
  now counts as a citation of the current chapter only when that chapter really has the number.
- **one more unit test** for that case (uncited caption ⇒ FAIL, and the message must not mention `图 7`) → 49.
- **stronger assertion**: `test_caption_without_chapter_number_not_given_fake_chapter` previously only
  asserted "3-7 absent", which survived mutation; it now also asserts `图 7` is present and
  `第 3 章 图 7` is absent.
- **docs**: the English README and `SKILL.md` 1.0.11 notes now record the ④/③ parallel-wording fix and the
  two-tier limitation note (previously only the Chinese README had them); the exit-2 list wording is
  "main causes (not exhaustive)".

### 1.0.11 (2026-11-22)
Fixed two defects found by the tenth-round reviewers (both were introduced or exposed by 1.0.10's
bare-number change), plus two documentation gaps:

- **crash on mixed reference keys**: with `--chapter` given and both a chapter-numbered citation
  (`图 2-9`) and a bare one (`图 9`) present, while the selected chapter has no captions, the code
  did `sorted({(key, n) ...})` over a mix of `None` and `str` → `TypeError: '<' not supported between
  'NoneType' and 'str'`; the process exited 1 via a traceback and printed no conclusion line (the 46
  unit tests were all green because no test mixed the two key types). Now sorted with
  `key=lambda p: (str(p[0]), p[1])`, and two regression tests cover it → 48 tests.
- **caption without a chapter number got a fake chapter label**: a caption `图 7` (global numbering)
  used to be keyed by the current `--chapter` value, so error messages could claim "chapter 3, 图 7"
  for a figure that carries no chapter at all. Captions now keep `None` as their key, matching how
  bare citations are keyed.
- **README_EN exit-2 list** now lists the same main not-executed causes as the Chinese README (it was
  missing "config top level is not a JSON object" and "this directory has a ledger but the config was
  found in an ancestor").
- **`README` ④ reworded** to be parallel to ③: there are two not-executed paths (only other chapters'
  figures cited; no captions and no citations here), not just one. Same fix in the Chinese README;
  `SKILL.md`'s v1.0.9 row now notes that its "≤80 chars" wording was superseded by the two-tier rule.

- **1.0.10** (2026-11-22): ninth independent review (U1 item-by-item re-run / U2 claim-vs-entity) —
  **not passing** (U1) / **passing with required fixes** (U2). Behaviour is fully fixed (chapter/number pairs,
  bare numbers, longer verbs, unittest 46), but two documentation defects remained:
  - **the spec paragraph still stated the old rule** (both reviewers): it said "a chapter that cites a figure
    while having no captions ⇒ FAIL; only 'no captions and no citations' is not executed", contradicting both
    the implementation and the 1.0.9 changelog — which made 1.0.9's "both READMEs and SKILL are aligned"
    untrue. Corrected to match the implementation (plus the pair-comparison and cross-chapter notes);
  - **an unreachable branch** (U1): the "same-chapter citation with no caption ⇒ FAIL" branch could never be
    reached (that case is already FAILed by the pair check); removed, comment rewritten;
  - **the known limitation was understated** (U2): it said "under 80 chars", but the separator branch allows
    **300 chars** (a 168-char prose paragraph with a space was accepted as a caption, A4 PASS exit 0);
    all three documents now state "80 without separator / 300 with separator";
  - **bare citations were mislabelled** (U1, low): «图 9» was reported as «图 3-9» because it was forced into
    the current chapter; bare citations are now keyed None (satisfied by that number in any chapter) and, when
    truly missing, reported as «图 9»;
  - the "verb + 了" pattern is widened to 1–8 characters;
  - two regression tests added (bare citation satisfied elsewhere / missing bare citation must not invent a
    chapter) → **unittest 46/46**.
- **1.0.9** (2026-11-22): eighth independent review (Q1 item-by-item re-run / Q2 claim-vs-entity)
  again judged **not passing** — the cross-chapter check was still wrong in the same way in both reports. Fixes:
  - cross-chapter dangling citations are now compared as **(chapter, number) pairs**: the previous version
    flattened all numbers into one set, so citing 图 9-9 looked satisfied by an existing 图 2-9 caption
    (with `--chapter 3` it exited 0 — a false PASS);
  - a chapter that only cites **another chapter's** figure (and has no captions of its own) is now reported
    honestly as *not executed* with an explanation, instead of claiming "this chapter has neither captions
    nor citations" — the 1.0.8 wording was claimed fixed while the code was untouched (a hollow claim);
  - the "verb + 了" pattern now allows 1–6 characters, so 详细描述了 / 进一步给出了 are recognised as prose;
  - **known limitation (stated honestly)**: prose without sentence-final punctuation whose verb is not of
    the "X 了" form can still be taken as a caption — the cap is **80 characters when no separator follows the
    number, 300 characters when a separator (space / full-width space / colon) does**. The 1.0.8 claim that
    the length cap covers it was too strong and has been removed (**1.0.10 correction**: this note previously
    said "under 80 chars" only, missing the 300-char separator branch). Trade-off unchanged: a false PASS is
    worse than a false FAIL;
  - three regression groups added (cross-chapter, longer verbs) → **unittest 44/44**.
- **1.0.8** (2026-11-22): seventh independent review (P1 item-by-item re-run / P2 claim-vs-entity)
  again judged **not passing** — all six behavioural fixtures passed, but one **claim-vs-entity** mismatch
  and one cross-chapter miss were found:
  - prose markers now use a **"verb + 了" pattern** (`^(?:中)?[\u4e00-\u9fa5]{1,3}了`) instead of an
    enumeration: the previous list had 展示了 but not 显示了, so "图 2-1 显示了…" plus a citation still
    reported "bidirectional OK" and exited 0;
  - `所示 / 所示为 / 中给出 / 中列出` were **removed** from the marker list — they introduce **noun-phrase
    captions** ("图 2-1 中给出的开度分布"), which the list wrongly rejected (exit 1);
  - **cross-chapter dangling citations**: citing a number that has no caption anywhere in the document
    (e.g. 图 9-9) is now a FAIL; previously it was filtered out per chapter and reported as not executed;
  - docs aligned (marker wording in both READMEs, the "this chapter cites another chapter's figure"
    wording, and README_EN's exit-3 list now includes "config top level is not a JSON object");
  - three regression test groups added → **unittest 41/41**.
- **1.0.7** (2026-11-22): sixth independent review (Z1 item-by-item re-run / Z2 claim-vs-entity plus
  41 counter-examples) again judged **not passing** — Z1: 9 of 10 truly fixed; Z2: 4 of 10 not. Fixes:
  - **caption heuristic missed both ways**: a 98-character paragraph "图 2-1 展示了…" plus a citation was
    still taken as a caption (the marker list only held un-suffixed verbs such as 显示/给出 and missed the
    common 展示了/描绘了), while a genuine caption "图 2-1 对应的开度分布" was wrongly rejected. Two rules
    now: ① a paragraph ending in sentence punctuation (。！？) is prose, not a caption (Chinese captions do
    not end in a full stop); ② markers immediately after the number are the **"verb + 了" form**
    (展示了/显示了/给出了/描绘了/记录了/中给出了 …, matched by a pattern rather than an enumeration —
    enumerations always miss one), plus 所示/所示为/可以看出/可知/因此; un-suffixed 对应/显示/给出
    are **not** markers (they are noun-phrase captions);
  - **known limitation of the sentence-final-punctuation rule** (stated honestly; it is a deliberate
    trade-off, not a bug to report again): any paragraph ending in 。/！/？ is treated as prose, so a
    genuine caption written with a trailing full stop ("图 2-1 五组裂隙的开度场分布。") is reported as
    prose (A4 then says "the body cites figures but there is not a single caption"). The trade-off: taking
    prose for a caption produces a **false PASS** (dangerous), while taking a caption for prose produces a
    **false FAIL** (visible and easy to fix by reformatting). Chinese journal style (and GB/T 7713) does not
    end captions with a full stop. **Recommendation: do not end figure/table captions with a full stop**;
    if your style requires it, this assertion will conservatively fail — review that one item by hand.
  - **dangling citations are now judged document-first**: with `--chapter 3` whose body cites a figure from
    chapter 2 while the document has no captions at all, the check used to be reported as "not executed"
    and passed (exit 0). Now: no captions anywhere + a citation anywhere ⇒ FAIL, regardless of `--chapter`;
  - **the `banned_terms` exit code was an empty promise**: README/SKILL claimed a wrong type there makes
    `dept_gate` exit 3, but the gate never reads the field. The docs now say only what is true — the gate
    validates that the config's **top level is a JSON object** (exit 3); the `banned_terms` type check lives
    in `check_doc` (string ⇒ exit 2);
  - **`workflow.md` exit 3** no longer mentions a non-existent "dependency missing"; it lists the four real
    causes (config not found / unparseable / top level not an object / own ledger present but config found
    only in an ancestor).
  Regression: 8 caption cases (real tab, ideographic space, sentence-final punctuation, genuine caption not
  rejected), the real chapter-2 docx, four gate scenarios, unittest 38/38.
- **1.0.6** (2026-11-22): fifth independent review (Y1 item-by-item re-run / Y2 claim-vs-entity plus
  counter-examples) again judged **not passing** — Y1: 9 of 11 truly fixed, 2 not; Y2: 8 of 11 hold,
  3 partly, plus one **P1 false PASS**. Fixes:
  - **a body paragraph mistaken for a caption => A4 false PASS**: an 86-character paragraph beginning
    `图 2-1 所示的…` plus one citation was treated as a caption, so A4 reported "bidirectional, consistent"
    and exited 0. Now a **prose marker immediately after the number** (所示 / 显示 / 可见 / 表明 / 说明 /
    对应 / 给出 / 表示 / 呈现 / 可以看出 / 可知 / 因此) makes it prose; the separator branch is capped at
    **300 chars** (real long captions with (a)(b) survive), the no-separator branch stays at **80 chars**.
    The check looks only at the text immediately after the number — checking the whole paragraph would
    kill real captions, which often contain 对应 in the middle (we hit that once).
  - **separator literals**: the code compared against two-character strings `\t` / `\u3000` instead of a
    real tab / ideographic space, so long captions using those separators were reported as "no captions".
  - **fallback marker crossing lines**: `\s*\d` could span a newline and turn `如图` + newline + `3 号点`
    into a figure number; now inline whitespace only.
  - **dangling citation under `--chapter N`**: if that chapter's body cites figures but the chapter has no
    captions at all, it is now a **FAIL** (was "not executed"); only "neither captions nor citations in
    this chapter" counts as not executed. Docs and code now agree.
  - **`~~~` fences**: `strip_fences` only knew ```; now both fence characters are recognised (same
    character must close the fence).
  - **exit 3 wording**: dropped the non-existent "missing dependency", listed the four real causes.
  - **FAIL outranks not-executed**: a definite FAIL is no longer downgraded to NOT RUN when fewer than
    three structural assertions ran.
  - 8 new unit tests for caption detection and dangling citations (unittest 38/38).
- **1.0.5** (2026-11-22): fourth independent review (X1 item-by-item re-run / X2 claim-vs-entity plus
  counter-examples) again judged **not passing**. Fixes:
  - captions such as `图2-1示意图` (number immediately followed by the title, no space or colon) were not
    recognised and caused a false FAIL; the rule was relaxed at the time (any paragraph starting with
    图/表 + number counted, <=80 chars). **That relaxation went too far — see 1.0.6.**
  - the fallback claiming "unrecognised numbering => FAIL" was unreachable: `图（2-1）` still exited 0;
    the fallback now also matches parenthesised numbers, so the claim holds;
  - `check_doc.py` now applies the same ancestor-config rule as the gate (this directory has its own
    ledger but the config was found above => exit 2), and an explicit `--config` really waives it;
  - `dept_gate.py` now honours an explicit `--config` (the hint promised an escape hatch that did not work);
  - fenced code blocks are blanked before scanning, so example snippets in a board (`## 当前板块`,
    `- [ ] D9`) can no longer fake or block a section;
  - reference-section headings accept `参 考 文 献` / `参考文献：`, and an unrecognised heading now lists
    the accepted forms;
  - exit-code ownership is stated per script (gate: 3; checker: 2); the A4 claim "cited figure without any
    caption => FAIL" is qualified as applying only without `--chapter`; `manifest.yaml` exit 3 description
    completed; `tests` `__main__` moved to the end of the file (direct run used to execute 24 of 30 tests);
    evals #6 prompt now carries the "will be cited as a baseline" premise that makes it critical.

- **1.0.4** (2026-11-22): third independent review (W1 mechanical re-run / W2 counter-example and
  consistency) again judged **not passing**: W1 found 26 items (18 fixed / 7 partial / 1 unfixed) plus
  10 new problems; W2 added 2 P1 and 5 P2. Fixed by **failure mode**, not by item:
  - a debt bullet written as `* [ ] D1` was skipped entirely (gate said "0 open debts"); all Markdown
    bullet markers are now accepted, and `workflow.md` states that **the checkbox is self-reported** —
    the gate does not verify evidence, reviewers do;
  - the gate could audit an **ancestor project's** config/ledger and exit 0 while this project's own
    debts were never read; that case now exits 3 and names the missing local config;
  - config type is validated, but **each script only validates the fields it reads**: `dept_gate.py` checks
    that the config file's **top level is a JSON object** (otherwise **exit 3**) and never reads
    `banned_terms`; the `banned_terms` type check lives in `check_doc.py` (a string ⇒ **exit 2**);
  - numbering regexes used `\s*`, so "图" at the end of one paragraph plus "3" at the start of the next
    formed a fake number and a valid document was reported as mixing styles; only in-line whitespace is
    allowed now;
  - with `--chapter N`, "no figures in this chapter" was wrongly turned into FAIL by the fallback gate;
    the fallback now only applies without `--chapter`, and its message says "numbering style unsupported"
    rather than "not executed";
  - `图 2-1：title` (colon captions) were not recognised; text after a reference list ("致谢",
    "Appendix") was parsed as reference entries — both caused false FAILs and are fixed;
  - author-year references were reported as "bidirectional" while only one direction was checked — now
    stated honestly;
  - the panel mechanism's admission was recorded as "user request, not an incident", which contradicted
    admission question 2; question 2 gained an explicit **user-request exception** (record it as a user
    request, never dress it up as an incident, and write down what would make you remove it).
  Regression: 8/8 smoke fixtures, 30/30 unit tests, real chapter document and real project gate pass as
  expected. Regression evidence is kept in the author's session locally (not distributed).
- **1.0.3** (2026-11-22): the second independent review (mechanical / consistency-adversarial) judged the
  package **not passing**: 26 findings each plus 9 new issues. Fixed: two numbering regimes supported and
  mixing judged FAIL; unrecognised numbering is FAIL rather than "not executed"; captions compared per
  chapter instead of by union; a bad `--config` or bad JSON exits 2; `--root` added; a missing debt
  section exits 1 instead of warning; case-insensitive and multi-section debt scanning; honest wording
  for zero warnings and for the cwd dependency; version and changelog statements aligned with reality.
- **1.0.2** (2026-11-22): the three-reviewer L2 blind panel judged the package **not passing**
  (fail / pass-with-fixes / fail). Fixes F1–F10 landed: critical baseline re-check unified on "all";
  `check_doc.py` no longer treats not-run as pass (missing config exits 2, A3 skipped without
  `--chapter`, fewer than 3 structural assertions exits 2, bare chapter numbers now detected);
  `dept_gate.py` counts only `- [ ]` as open debt (an exemption note no longer deadlocks the gate),
  ledger wording matches what is actually checked, and a mismatched `project_name` raises a warning;
  the cwd dependency is stated honestly; panel isolation is "by construction"; dead README reference
  removed; project-specific names purged from tests/evals; manifest exit codes scoped to the gate and
  a missing-asset policy added. Regression evidence is kept in the author's session locally (not distributed with the package, so no path is given here).
- **1.0.1** (2026-11-21): added the multi-reviewer panel mechanism — triggers, distinct-anchor
  composition, devil's advocate, no-cross-visibility, verdict rules (`references/blind-review.md`;
  `critical.md` gains the trigger pointer; `manifest.yaml` condition updated). Basis: the user's
  judgement that panels will be useful and prevent large errors; composition absorbs external
  practice (distinct anchors, EIC + devil's advocate), triggers per admission question 2 stay on
  real scenarios (baseline role / prior miss / explicit request) — no standing panel.
- **1.0.0** (2026-11-21): first release, distilled from a real project's department practice
  (review caught 8 errors the author's self-check had ticked as done, and 5 baselines turned out
  to be the wrong ruler).
