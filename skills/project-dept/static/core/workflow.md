# The six-step flow

The Lead runs these six steps. Steps 0 and 1 happen before any work is started by anyone.

## Step 0 — Run the gate

```bash
python <skill>/scripts/dept_gate.py
```

| exit | meaning | what the Lead must do |
|---|---|---|
| `0` | pass | warn items are printed; carry them into the next reply to the user |
| `1` | blocked — structural problem | fix it; **do not start work** |
| `2` | needs a decision | close each open debt as **做掉 / 豁免（理由 + 复查日期）/ 降级**, then re-run |
| `3` | not executed | four causes: config file not found / config unparseable (bad JSON) / config top level is not a JSON object / this directory has its own ledger but the config was found only in an ancestor (auditing with an ancestor's config would miss this project's debts) — fix, and say plainly "gate not executed" if you proceed |

**Debt notation (the gate parses it literally, so write it this way):**

- an **open** debt MUST be a bullet that starts with an unchecked box: `- [ ] **D3** what is still owed`;
  any Markdown bullet marker works (`-`, `*`, `+`) — the gate accepts all three, because a real
  debt written as `* [ ] **D3** …` used to be skipped entirely (gate reported "0 open debts");
- a **closed** debt starts with a checked box: `- [x] **D3** what was done, where the evidence is`;
- a waiver is a **note, not a debt**: write it without a box, e.g. `- D3 waived until 2026-11-25: reason …; recheck on …`;
- **the checkbox is self-reported.** The gate only reads the box; it cannot verify that the evidence
  exists. Cross-checking a closed debt against its evidence is the reviewer's job (L2), not the gate's.
  Do not read "exit 0" as "every closed debt was verified";


- the section heading must contain one of `未完成事项 / 债务账本 / open debts / debt ledger` (case-insensitive);
  **no such section ⇒ exit 1** (the gate refuses to open a package it cannot audit), and every matching section is scanned,
  not just the first one.

**Why the notation matters:** a real debt written as a plain bullet is invisible to the gate — it will report
"0 open debts" and let you start. That is the same failure mode as an unchecked assertion: the check runs, finds nothing,
and passes.

Never claim the gate passed when it did not run. If the environment cannot run it, check the same items by hand, and write "gate not executed, checked by hand" in the reply.

## Step 1 — Read the base

Read, in this order, only what exists:

1. the project charter (what this project is, hard rules, path table, environment traps, domain conventions);
2. the flow document (state machine, gates, role permissions) — usually the long one;
3. the board (current work package + debt ledger + frozen list).

Do not read the whole archive. If the charter points at a "current package" and there is none, **stop and ask the user** which package to open — do not invent one.

## Step 2 — Scope the package (立项)

Write the package sheet before touching anything:

- **goal** in one sentence;
- **deliverables**: path + form;
- **acceptance standard**: judgeable pass/fail per item, written by the Lead, not by the executor;
- **participants** and their write scopes;
- **out of scope** (frozen list) — what this package explicitly will not do;
- **rigor** axis value, and what extra checking that implies.

Only one package may be active at a time.

## Step 3 — Break into tasks

For each task record: definition-of-ready, write scope, dependencies, acceptance standard. Keep a task to roughly half a day of work. Tasks that cannot be verified separately should be merged; tasks that block each other get `blocked_by`.

If the host has no shared task board, use the board file as the same ledger — the discipline is what matters, not the tool.

## Step 4 — Staff it

- Give each participant the **full role card** for its role, then the task sheet. Never improvise a role description on the spot — that is how environment traps get re-learned every time.
- Roles are a capability pool, not a parallel production line: participants the package does not need stay idle and do not self-assign work.
- For each participant, state exactly which paths are readable, which are writable, and which are frozen.

## Step 5 — Run the loop

Deliver → L1 self-check → L2 independent review → L3 final judgement → close.

- The executor never marks its own task complete.
- The reviewer writes an independent conclusion first, then may compare with the self-check.
- The Lead also probes at least one thing itself at L3 — "the reviewer said OK" is not a judgement.

## Step 6 — Close and archive

- Record the result in the delivery register (date, package, artefact, acceptance verdict, evidence path).
- Update the board: package status, debts found, frozen list.
- Fill the direction pre-mortem three questions (see `references/self-skepticism.md`).
- Only then open the next package.

Closing does not mean "verified" if anything was waived — write `未验收（存档）` in the first line of the record when a package is closed for bookkeeping reasons only.
