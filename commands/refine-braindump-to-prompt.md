---
name: refine-braindump-to-prompt
description: Lapidate ONE raw braindump into ONE executable prompt (RECOVER -> DRAFT -> REFINE -> RED-TEAM -> RENDER), after a deterministic lint pre-pass that collapses synonym verbs, halts on unbound placeholders and on secrets bound for a public sink, and bounds self-referential meta-dumps to one pass.
---

# /refine-braindump-to-prompt Command

Invokes the `refine-braindump-to-prompt` skill (soul-name *Lapidary*).

## Usage

```text
/refine-braindump-to-prompt "<braindump-path-or-text>" [--architecture default|gauntlet-loop]
    [--dry-run] [--output table|list|json|json-rpc] [--output-target <kind>[:<param>],...]
```

## What it does

1. Runs `scripts/lint_braindump.py` from the skill's own base directory on the dump. Exit 1 ->
   HITL (`empty-dump` -> error); exit 2 -> error; script missing -> stop and report it.
2. Runs the five phases of the skill and renders ONE prompt plus a machine envelope.
3. A dump that also asks for a reusable tool gets a `handoffs[]` record naming
   `agentic-tool-forge`. The command does not dispatch it; the caller passes the rendered
   prompt to the forge.

It never executes the prompt it renders.

See `skills/refine-braindump-to-prompt/SKILL.md` for flags, stop rules and the output contract.
