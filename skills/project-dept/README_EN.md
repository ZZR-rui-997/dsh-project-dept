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
manifest.yaml                axes (deliverable / rigor) + conditional loading + two quality tools
static/core/
  principles.md              non-negotiable stance + provenance classes [Origin]/[External]/[Own]/[None]
  workflow.md                six-step run method (including gate exit codes)
  output-contract.md         artefact name + required sections + blocking conditions
static/fragments/
  deliverable/{document,code,data,model}.md    loaded by delivery type
  rigor/{exploratory,standard,critical}.md     loaded by "what happens if this is wrong"
references/                  on-demand depth (baseline / blind review / self-skepticism / mechanism choice / anti-patterns / scaffolding)
scripts/
  dept_gate.py               pre-start gate (reads dept.config.json)
  check_doc.py               mechanical assertions for documents (eight checks)
```

## The two scripts

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

Both scripts use only the standard library (`check_doc.py` additionally needs `python-docx`),
resolve paths relative to themselves or to the config, and hard-code no machine paths.

## Standing it up in a project

See `references/project-scaffold.md`: create the `_team/` ledger, write `dept.config.json`,
write role cards, seed the baseline register, wire the two scripts, run a smoke package.
Moving to another project means repeating those seven steps; moving to another machine means
copying `~/.dsh/skills/`.

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
