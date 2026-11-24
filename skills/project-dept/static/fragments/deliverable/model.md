# Deliverable: model

A structured or binary artefact produced by a tool: geometry, mesh, simulation case, CAD, drawing.

## Checks that matter

1. **Parameters actually used are recorded** — not the parameters intended. Dump the realised settings from the case/solver and store them next to the artefact.
2. **Provenance of the generator** — which script/version produced it, and whether that script is under version control.
3. **Binary equality is not correctness** — identical md5 proves the same bytes, never the same physics. Use it only to prove "nothing changed", never to prove "it is right".
4. **Consistency between artefacts** — mesh vs geometry (dimensions, element counts, coordinate units), case vs declared matrix (physical duration, time step, boundary values).
5. **Re-openable from scratch** — the reviewer regenerates or re-opens the artefact from the archived inputs, and compares a quantitative summary (counts, extents, totals), not a screenshot.
6. **Declare the deviation** — if the built artefact differs from the declared matrix (coarser grid, shorter duration, different parameter value), it goes on the record explicitly.

## Review emphasis

- Compare against the *declared* specification, not against the previous run of the same case.
- Check units and frame conventions at the boundary (SI vs mm, absolute vs gauge) — most silent breakage is here.
- For simulation artefacts, verify stability/consistency indicators were within limits (e.g. Courant number), not just that the run finished.

## Common traps

- Trusting a parameter report read back from the tool when the tool silently ignored the setting.
- Judging a mesh by its statistics only; a single inverted or degenerate element can ruin a run while the summary looks fine.
- Comparing absolute pressures in an incompressible formulation where only differences matter.
- Believing "it completed" means "it converged".
