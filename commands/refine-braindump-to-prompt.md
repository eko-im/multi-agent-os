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

1. Runs `skills/refine-braindump-to-prompt/scripts/lint_braindump.py` on the dump (exit 1 -> HITL).
2. Runs the five phases of the skill and renders ONE prompt plus a machine envelope.
3. A dump that also asks for a reusable tool is handed to `agentic-tool-forge` via `handoffs[]`.

It never executes the prompt it renders.

See `skills/refine-braindump-to-prompt/SKILL.md` for flags, stop rules and the output contract.
