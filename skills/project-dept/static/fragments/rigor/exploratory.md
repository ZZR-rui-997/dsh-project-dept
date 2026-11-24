# Rigor: exploratory

The conclusion only steers the next internal decision. Nothing is published, nothing is quoted, and being wrong costs a re-run.

## What applies

- L1 self-check only. A formal blind package is not worth its cost here.
- Record what you did and what you assumed, in a few lines — enough that you can reconstruct it in a week.
- Keep the artefacts. Cheap now, expensive to regenerate later.

## What still does not relax

- **No invented numbers.** "未验证" is always allowed; a guessed number is not.
- **Write scope.** Do not touch files outside the declared scope, even to "clean up".
- **Say what you skipped.** "Explored A and B, did not look at C" is a complete statement; silence about C implies it was covered.

## Cheap habits worth keeping

- One command that reproduces the run, pasted into the note.
- The realised parameter/configuration dump next to the output.
- If the exploration produced a number you might later rely on, write down the definition used — the definition is what gets lost, not the digits.
