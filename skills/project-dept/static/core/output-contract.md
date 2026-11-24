# Output contract

## Default deliverables per artefact class

```text
document : <name>.docx | <name>.md
code     : <repo-relative path> + a one-command way to run it
data     : <table>.csv | <results>.md  + the script that produced it
model    : <case dir> + a setup/run note + the parameter table actually used
```

Every work package additionally requires two working artefacts (not deliverables, but mandatory):

```text
自检_<task>.md      L1 self-check, ticked item by item against the declared acceptance standard
复核单_<task>.md    L2 reviewer's independent conclusion, written before seeing 自检_<task>.md
```

For `rigor: critical`, a third artefact is required:

```text
基准核对_<task>.md  every baseline used re-checked against originals (not a sample — all of them,
                    matching the rigor:critical rule in static/fragments/rigor/critical.md)
```

## What the hand-over message must contain

Keep it under 300 words:

1. artefact path(s);
2. **one reproducible command** that regenerates or re-verifies it;
3. the ticked self-check table (one line per acceptance item);
4. unresolved items — explicitly, even if empty ("none" is allowed, silence is not).

## Evidence-status header

Every formal hand-over begins with this block so the reader knows the evidential weight before reading:

```markdown
> 覆盖范围: 全部 / 部分 / 仅摘要或元数据 / 仅口述
> 验证方式: 独立重算 / 外部权威核对 / 仅自洽性检查 / 未验证
> 基准出处等级: [Origin] 若干 / [External] 若干 / [Own] 若干 / [None] 若干
> 检查强度: 仅 L1 / L1+L2 / L1+L2+L3
> 未覆盖项: 无 / 具体列明
> 交付完整度: 相对给定输入完整 / 部分
```

`相对给定输入完整` does not mean the content is correct — it means nothing known was left out.

## Quality gates

Block the hand-over when:

- a headline number cannot be traced to a locator;
- the artefact claims full coverage while only part of the input was read;
- author-stated limitations and reviewer criticism are mixed into one undifferentiated block;
- an `[Own]` value is presented as if it were `[Origin]`;
- content was invented to fill a slot;
- the declared acceptance standard was silently changed during the work.

If a blocker cannot be resolved, downgrade to `部分` and name the exact gap. A failing tool run blocks delivery; a passing tool run does **not** prove correctness.
