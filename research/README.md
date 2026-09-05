# Research

Evidence for the ENB compatibility work. Kept separate from `docs/` on purpose:
`docs/` says how to use the thing, this says what is actually known.

| File | What it holds |
|---|---|
| [STATUS.md](STATUS.md) | where the project stands, what is settled, what is open, what to do next |
| [regular-enb-review.md](regular-enb-review.md) | September 5 review: ordinary ENB baseline defects, omitted renderer dependencies, and exposure evidence limits |
| [legacy-shader-bridge.md](legacy-shader-bridge.md) | September 4 reopening: historical shader mappings, standard D3DX effect validation, and concrete translation boundaries |
| [research-log.md](research-log.md) | one entry per session: configuration, hypotheses, observations, conclusions, next experiment |
| [enb-contract.md](enb-contract.md) | the interface ENB expects, where it is written down, and how CE and FusionFix each measure against it |
| [contracts/](contracts/) | machine-readable interface contracts for `tools/shader_dump/check_interface.py` |
| [rendering-pipeline.md](rendering-pipeline.md) | how FusionFix builds and loads shaders, and every place it touches D3D9 |
| [feature-conflicts.md](feature-conflicts.md) | the feature map, category A–D classification, and the evidence behind each conflict |
| [proxy-chain-results.md](proxy-chain-results.md) | who loads whose `d3d9.dll`, and the permutations still to test |
| [test-matrix.md](test-matrix.md) | the six configurations and twelve scenes every result is measured against |
| [failure-log.md](failure-log.md) | one classified entry per observed failure |
| [shader-map.json](shader-map.json) | ENB `shaderinput` hash → the game shader it replaces, per shader set |
| [shader-map.schema.json](shader-map.schema.json) | schema for the above |

## The short version

The current evidence is in [STATUS.md](STATUS.md) and
[legacy-shader-bridge.md](legacy-shader-bridge.md). ENB 0.163's actual hash is now
recovered. Stock CE's postfx shader is recognized through an alternate hash,
but none of iCEnhancer's twelve original shaderinput filenames matches stock CE
on disk. Three terrain filename aliases and a visible diagnostic probe were
staged; the user's corrected probe run produced localized magenta terrain with
all three files verified in place. This confirms runtime substitution for at
least one member of the combined terrain group. Five weaker candidates remain
separate.

The normal aliases subsequently rendered textured ground at the same location
with the diagnostic color removed. Visual correctness remains uncertain because
other shader/postfx failures affect the frame. A new first-bind trace and offline
report now checks exact assembled replacements automatically in one ordinary
scene; see [the focused test](alias-test.md).

The iCEnhancer effects are ordinary compiled D3D9 effects that load and bind in
an isolated Microsoft D3DX harness without their ASI. Historical FusionFix
provides named role/interface mappings across 1.0.7.0/1.0.8.0/CE. Modern FusionFix
changes bindings and depth representation as well as bytecode identity.

Full iCEnhancer rendering remains unproven. Existing ASI crash dumps reveal
changed executable instructions, but not their writer. Earlier blanket claims
that CE shader identities are unchanged, that an opaque effect runtime makes
the task impossible, or that retaining 89% of blobs retains 89% of graphics
features are superseded. Further PC/game tests are performed by the user:
[focused test instructions](alias-test.md).

## Conventions

* Every claim says whether it was measured, read out of source, or assumed.
* A shader-map entry marked `confirmed` means a runtime capture showed ENB
  substituting that shader. Nothing else earns that word.
* Failure-log entries get exactly one category. Two categories means two
  entries.
