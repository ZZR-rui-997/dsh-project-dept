# Standing the department up in a new project

Ten minutes of setup, then the department runs. Nothing here is machine-specific; fill the blanks with the project's own values.

## 1. Decide where the rules are injected

Two locations matter:

- **user-global instruction file** (applies to every project on this machine) — put only the rules that must never be forgotten and have no project-specific content;
- **project instruction file** at the project root (applies to sessions whose working directory is inside this project) — put the project identity, the hard-rule summary, the skill routing table, the environment traps, and where the ledger lives.

Keep the instruction file **short**. It is injected into every request; a long one is read once and obeyed never. Deep detail belongs in the ledger files, loaded on demand.

Note for the reader: a session that was already running when you edit the instruction file will not reload it. Say so explicitly to the user rather than assuming the new rule is in force.

## 2. Create the ledger directory

```text
_team/
  README.md               charter: hard rules, path table, environment traps, domain conventions, this project's terminology
  工作流.md               flow: state machine, gates, role permissions, quality gates (the long one)
  看板.md                 board: current package, debt ledger, frozen list, pending decisions
                        (debt ledger format: `- [ ] **D1** open …` / `- [x] **D1** done …` / `- D1 waived until <date>: …`; heading must contain 未完成事项 / 债务账本 / open debts / debt ledger)
  交付登记簿.md           delivery register: one row per closed package
  基准清单.md             baseline register: every item used as a baseline, with class and locator
  岗位/                   role cards, one per role
  templates/              task sheet, review sheet
   bin/                    pointer note for the quality tools (default: call them from the skill;
                         a copy is allowed only as an unmodified snapshot for offline reproducibility)
  out/<role>/              produced artefacts, one subdirectory per role
  review/blind/<task>/    blind packages and review sheets
```

Only create what the project will actually maintain. Every extra file is a future inconsistency.

## 3. Write the config file

`dept.config.json` at the project root (or anywhere the gate can find by walking up):

```json
{
  "project_name": "<name>",
  "ledger_dir": "_team",
  "board_file": "看板.md",
  "flow_file": "工作流.md",
  "register_file": "交付登记簿.md",
  "baseline_file": "基准清单.md",
  "role_dir": "岗位",
  "required_roles": ["lead", "audit", "reviewer"],
  "artefact_dir": "out",
  "scratch_patterns": ["probe_*", "_scan*", "_summ*", "_tmp*"],
  "banned_terms": [
    {"pattern": "<wrong variant>", "reason": "<correct form>", "flags": "i"}
  ],
  "environment": {
    "notes": ["<machine-specific trap worth remembering>"]
  }
}
```

Rules:

- paths inside the config are **relative to the project root**;
- `banned_terms` is where a project's own terminology lives — never inside the script;
- `required_roles` lists only the roles this project actually uses.

## 4. Write the role cards

One file per role, same eight sections every time:

1. **position** — where it sits, who it answers to;
2. **responsibilities** — what it does, and explicitly what it does not;
3. **inputs** — what it must read before starting;
4. **outputs** — artefacts, paths, and the hand-over format;
5. **known environment traps** — only traps actually hit on this machine;
6. **acceptance standard** — how its own work will be judged;
7. **hand-over** — how it reports, and to whom;
8. **changelog**.

`lead`, `audit`, `reviewer` can start as near-verbatim copies of the generic role templates. Domain roles (`sim`, `write`, `geom`, or whatever the project needs) must be written by someone who knows the domain traps — copying generic text there is how the traps get re-learned.

## 5. Seed the baseline register

List every item currently used as a baseline and give it a class and a locator. Expect to find several `[Own]` items masquerading as `[Origin]` — that is the point of doing it early.

## 6. Wire the quality tools

Wire every script listed under `quality_tools` in `manifest.yaml` (do not assume a fixed number — the list grows):

- **gate** (`dept_gate.py`) — runs before a package opens and before every report to the user;
- **checker** (`check_doc.py`) — runs before a document artefact is handed over;
- **package self-lint** (`check_skill.py`) — runs after you edit the skill package itself;
- **eval runner** (`run_evals.py`) — `static` schema check always; `judge`/`tally` for blind A/B scoring;
  `grade` is deprecated (12/12 false FAILs on real answers) and must not be used as an acceptance
  criterion, and `compare` (built on grade) is a direction hint only.

Prefer calling them from the skill's `scripts/` directory with the project config path (`--root` / `--config`); `bin/` in a fresh scaffold is a **pointer note, not a copy**. Copying *is* allowed when a package must be reproducible offline — but then it must be an **unmodified snapshot**, its sha256 must be recorded in the ledger, and it must be re-synced when the skill version changes. Do **not** edit the copy: a per-project fork of a generic checker means the audit is now measuring something different from what the skill describes.

Verify the wiring by running each once and confirming the exit codes behave as documented — in particular that the gate exits `1` when the ledger is structurally broken, and that the checker can be made to fail.

## 7. First run

Open a small, genuinely useful package as a smoke test, run the full flow (Step 0 gate, then Steps 1-6), and close it. If step 6 (archive) feels like paperwork, shorten the record template now rather than skipping it later.

## Migration from an existing project

If the department already exists in a project and you are converting it to this skill:

1. copy the project's own content (charter, role cards, board, register) as-is — they stay in the project;
2. replace the generic parts with references to the skill;
3. keep the project instruction file but trim it to project identity + hard-rule summary + routing;
4. run the baseline register and the gate before declaring the migration done — a migration that has never been executed is a rename, not a migration.
