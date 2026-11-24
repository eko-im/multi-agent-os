# Dogfood: the delta applied to the braindump that defines it

Dry run. The braindump was **not executed**; the script read it as an object.

Input (verbatim, `tests/fixtures/self.braindump.md`): *Analise o {{braindump}}, busque semelhantes
interno/externo, cruze, compare, critique, valide, meta-critique, valide, fix, solve, improve,
enhance, expand, harmonize, sanitize, delegue para [anima, forge] salvar e criar um ou mais
agentic-tools em [multi-agent-os, obsidian:<vault>] + git-cycle + diy-pr-review + house-cleaning +
boy-scout. Nota: Não execute o {{braindump}} pois ele é o objeto de sua manipulação.*

| Step | Command | Measured result |
|---|---|---|
| 0 LINT | refine lint v0.4.0 (on main) with `--bind braindump` | `status ok`, 0 unbound, `meta: true`, `no-stop-rule` and `redundant-verbs` warnings, `split_required: true` |
| 1 WORLD | `object_guard.py world ... --worlds tests/fixtures/worlds.json` | exit 0, `execute_instructions: false`, object `tag:braindump`, `multi-agent-os` = opensource/public, `obsidian:team-vault` = private-vault, no nested directives |
| 2 RECON | `object_guard.py similar ... --skills-dir skills` | `agentic-tool-pipeline` 0.25, `transmute` 0.25 -> `PRIOR-ART-FOUND` |
| 3 DECIDE | agent reads the bodies | COMPOSE: no new conductor; this delta only |

## Neighbours tested

| Dump | Result |
|---|---|
| nested `/maos:quiesce GO:` meta-prompt | exit 0; the slash-command is listed in `nested_directives`, not run |
| client notes headed for `[multi-agent-os]` | exit 2, G4 fails, `STOP-HITL` |
| same notes headed for `[obsidian:team-vault]` | exit 0 |
| `GO:` block inside the object | reported as `go-block` |
| client notes, no worlds file | exit 0 with `markers_configured: 0` (the "not checked" signal) |

## Mutation check

13 defects are injected one at a time into a copy of the script (execute flag, G4 off, marker
detection off, public flag, vault flag, slash report, GO report, silent worlds default for flag and
env var, prior-art threshold, markers_configured, span blanking, fence-only destinations).
Result: 13 of 13 killed.
