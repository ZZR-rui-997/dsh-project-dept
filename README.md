# dsh-project-dept

An acceptance-first workflow skill for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness): run one complex piece of work as a **single reviewable board**, open it through a gate, review it with people who did not build it, and never let the author declare it done.

<sub>Chinese version: [README.zh.md](README.zh.md)</sub>

## Why

Agents can schedule work; they are bad at deciding whether the work is *correct*. "I split it into four agents and they all finished" says nothing about whether the deliverable survives someone trying to break it. This skill adds the missing half: a small, explicit protocol for opening, decomposing, delivering, and **verifying** a piece of work — and a script that blocks the start when the project's own bookkeeping says it is not ready.

## What you get

- **A `project-dept` skill** that loads when the user says things like "work this as a board", "spin up the team for this", or "the check has to be independent".
- **A `loop-ops` skill** that runs the bounded review loop on a deliverable that already exists: fresh reviewer thread → fix the must-fix list → a second fresh thread to confirm. Two rounds by default, a hard cap, state on disk, and an edit whitelist so the loop cannot wander.
- **An opening gate** — `scripts/dept_gate.py`. Exit `0` clears the work, `1` forbids it, `2` requires the lead to resolve every open debt item (fix, explicitly exempt with a reason and a recheck date, or downgrade the scope) before starting. Exit `3` means the gate never ran and must not be read as a pass.
- **Three-layer acceptance** — self-check, then **L2 blind review by someone who did not build the thing**, then a final pass. The reviewer may not see the author's reasoning first.
- **Baseline self-audit** — when the "known good" reference itself may be stale (an old report, an earlier audit note, a previous version), the baseline gets audited before it is used as truth.
- **A closed loop** — proposal → decomposition → execution → delivery → acceptance → archive, with a delivery ledger so "done" is a recorded decision rather than a feeling.

## Install

### As a bundle (recommended)

The skill is registered by the plugin itself through `ctx.skills.register()`, so installing the package is enough — nothing is copied into your config directory. Install it as a bundle through your profile's plugin manager (**Plugins → Add plugin**, pointing at the package directory or the published package), or from **Plugins → Discover** once it appears in the market index.

### As a plain skill

If you would rather not install a bundle, copy the skill directory straight into a scanned root:

```bash
# per project
cp -r skills/project-dept skills/loop-ops <your-project>/.dsh/skills/
# or for every project
cp -r skills/project-dept skills/loop-ops ~/.dsh/skills/
```

Both routes expose the same two skills with the same bodies; the bundle only saves you the copy and keeps them updated through package upgrades. `loop-ops` declares `project-dept` as its prerequisite: the loop fixes a deliverable, the three-layer acceptance in `project-dept` decides whether it is done.

## Use it

1. Add a `dept.config.json` to your project (the skill ships a template path and a scaffold reference) and an `AGENTS.md` that points at your ledger directory — by default `_team/`.
2. Before any work starts, run the gate:

   ```bash
   python scripts/dept_gate.py --root /path/to/project
   ```

3. Ask the agent to open a board. It will state the two axis values it detected (deliverable type and rigor level) in one line so you can correct it cheaply, then load only the fragments those values select.
4. Deliver through the three layers. The skill refuses to mark a board complete without an independent review record.

## What is inside

```
skills/project-dept/
skills/loop-ops/
├── SKILL.md                 # the protocol the model reads
├── manifest.yaml            # axes, always-load list, on-demand references
├── README.md / README_EN.md
├── VERIFICATION.md          # the review log: 14 revisions, what failed each time
├── references/              # deep-dives: blind review, baselines, anti-patterns…
├── static/core/             # stance, six-step workflow, output contract
├── static/fragments/        # fragments selected by the two axes
├── scripts/dept_gate.py     # the executable gate
├── scripts/check_doc.py     # document consistency checker
├── evals/evals.json         # routing and behavior cases
└── tests/test_helpers.py
```

`tests/bundle.test.js` (run with `node tests/bundle.test.js`) checks that the loader parses the shipped frontmatter, that the registry gets a complete definition, and that **every file the body tells the model to read actually exists in the package** — the skill itself treats a declared-but-missing file as a defect, so the bundle is tested the same way.

## Honest limitations

- **The skill body is written in Chinese.** The protocol is language-independent, but an English-speaking reader will be reading Chinese instructions. An English body is not shipped yet; the English README is a translated summary, not the skill.
- **`find_config` walks up from the current working directory**, so the gate finds `dept.config.json` only when the shell starts inside the project.
- **The gate needs Python 3** on `PATH` (or an explicit interpreter path).
- **No UI.** This is a workflow skill plus two scripts; there is nothing to look at beyond the plugin card.
- **It does not replace domain skills.** It decides *how* work is organized and accepted; the parameters and conventions of a specific field belong in that field's own skill.

## Verification of this package

`VERIFICATION.md` in the skill records how the protocol itself was hardened: every revision came from an independent reviewer rejecting the previous one, and the entries name the concrete counter-example that caused the rejection (a cross-chapter reference comparison that produced a false PASS, a mixed-key sort that crashed, and so on). That record is the reason to trust the workflow more than a prompt that merely sounds rigorous.

## License

MIT — see [LICENSE](LICENSE).