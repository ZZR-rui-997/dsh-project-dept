# Deliverable: code

Something that will be executed: a script, program, tool, or pipeline.

## Checks that matter

1. **Reproducibility statement** — one command, from a clean state, that reproduces the reported result. If it needs a data file or env var, say so explicitly.
2. **The check must be able to fail** — prove the checker is alive by feeding it a deliberately broken input and showing it reports the failure. A checker that has never failed is unverified.
3. **Read-only unless declared** — a verifier/checker must not modify anything. Anything that writes must declare its write scope.
4. **Script-owned paths, but config is found from cwd** — scripts resolve their own resources relative to the script file (no absolute paths baked into code; machine-specific paths belong in the project config). The project config `dept.config.json` itself is located by walking up from the working directory, so running from outside the project tree can pick up another project's config; pass `--config` / `--root` to pin it, and the gate warns when `project_name` and the directory disagree.
5. **Exit codes are a contract** — document each code; 0 must mean "everything passed", never "nothing ran".
6. **Missing dependency ≠ pass** — if a dependency is absent, exit with a distinct "not executed" code rather than a silent 0.

## Review emphasis

- The reviewer runs it, does not read it. Run it on a known-good input and on a deliberately broken input.
- Check the "pass" path is not vacuous: does any assertion actually have the power to fail?
- Confirm the reported result came from this code, not from the previous run of a different version.

## Common traps

- Counting table-cell text as body text (false positives).
- Supporting only one input dialect and treating the other as "nothing to check" (false PASS — the worst kind).
- Returning 0 when the required library is missing.
- Hard-coded absolute paths that work on the author's machine only.
- Replacing a bundled script with a home-made one mid-task — then the audit is measuring a different thing than declared.
