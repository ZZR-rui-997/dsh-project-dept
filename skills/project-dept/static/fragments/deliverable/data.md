# Deliverable: data

A dataset, result table, statistics, or computed result set.

## Checks that matter

1. **Provenance per column** — every column states where it came from: measured, computed (by which script), or transcribed (from which source).
2. **Units and conventions stated once, applied everywhere** — including sign conventions and reference frames.
3. **Independent recomputation of a sample** — the reviewer recomputes at least a few entries from the original data with an independent script, not by re-running the author's script.
4. **Producing script is archived alongside** — a result table without its generator is a rumour, not a result.
5. **Missing values are explicit** — never silently zero-filled, never interpolated without saying so.
6. **Rounding is declared** — the number of significant figures and whether the last digit is meaningful.

## Review emphasis

- Recompute, do not re-read. Re-reading the author's table confirms the author's arithmetic, which is exactly the mistake being guarded against.
- Check the *definition* used, not only the arithmetic: two people can compute the same quantity under different definitions and both be internally consistent.
- Verify any interpolated or extrapolated value stays within the range the source actually measured.

## Common traps

- Reporting a statistic whose definition was never fixed — the value reproduces only under one unstated convention.
- Averaging over a window that silently includes a startup transient.
- Quoting a derived quantity with more precision than the input allows.
- Presenting an internal reprocessing of earlier results as if it were independent measurement.
