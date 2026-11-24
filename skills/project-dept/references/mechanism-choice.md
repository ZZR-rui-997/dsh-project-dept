# Choosing where a mechanism lives

The governing principle: **use the weakest mechanism that suffices.** Stronger mechanisms cost more, fail louder, and are harder to remove.

Ordered from weakest to strongest:

| mechanism | what it is good for | cost | scope |
|---|---|---|---|
| a line in the auto-injected instruction file | rules that must apply without being remembered | near zero, but it is only text — it can be ignored | every session in this project (or every project, if placed in the user-global location) |
| a skill | a procedure with references, templates, and a trigger condition | writing it once | wherever the skill roots resolve |
| a script | anything that can be judged mechanically | writing plus maintaining it | wherever it is run |
| a host plugin | real-time interception, new UI surface, new tool | code, profile-level install, version coupling | the whole profile, all sessions |
| an agent preset | a different composition of capabilities for a session | configuration only | the session that selects it |

## Decision rules

- **"How to work" knowledge → skill.** Procedures, judgement rules, checklists, templates. Prose in a skill can be argued with; code in a plugin cannot.
- **"Is this correct" checks → script**, invoked from the flow at a named moment (start of a package, close of a package). A check nobody is told to run is a check that does not exist.
- **"Stop this right now" → host plugin**, and prefer one that already exists over writing your own. Real-time interception is the only thing a script cannot do.
- **"A different set of capabilities" → preset**, not a rewrite. Note that preset selection affects only later tasks; it does not retroactively change the current session.

## What belongs in project config, never in the script or the skill

- absolute paths of this machine, this project, this installation;
- the project's own terminology, its banned word variants, its reference style;
- values that come from the project's data.

A script that hardcodes a machine path works exactly once, on one machine, and then becomes a puzzle. A checker with the project's vocabulary baked in cannot be reused and quietly misfires on the next project.

## Script resolution rule

Resolve bundled scripts **relative to the skill directory**, never relative to the caller's working directory. Same for reading config: walk up from the working directory to find the config file rather than assuming a fixed location.

## When not to build anything

If the mechanism is meant to prevent an accident that has never happened, do not build it. Record the intent instead, and build it the moment the accident occurs. Speculative infrastructure is the most expensive kind: it costs maintenance forever and has never demonstrably prevented anything.

## Do not confuse a tool's limits with a rule's limits

Host-level capability boundaries are facts to discover and design around, not rules to invent. Ask the host's own documentation first; do not write a workaround for a mechanism that already exists and is simply not enabled.
