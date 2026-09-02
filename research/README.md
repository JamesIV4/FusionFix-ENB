# Research

Evidence for the ENB compatibility work. Kept separate from `docs/` on purpose:
`docs/` says how to use the thing, this says what is actually known.

| File | What it holds |
|---|---|
| [STATUS.md](STATUS.md) | where the project stands, what is settled, what is open, what to do next |
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

ENBSeries recognises a game shader by hashing its bytecode and substitutes the
assembly in `shaderinput/psh<HASH>.txt`. It documents the interface it expects
from the game in `enbeffect.fx`, in plain text.

Measured against that:

* **Complete Edition still honours it.** Four of CE's post-process shaders match
  ENB's declared parameter table on all twenty entries, and three of the twelve
  shaders the preset targets match CE's disassembly at similarity 1.000. CE did
  not rewrite the shaders these presets care about.
* **FusionFix does not.** All 1689 shaders in its package have different
  bytecode; only 2 of 638 distinct stock shaders survive byte-identical. Its
  post-process shaders carry no reflection data at all and have grown
  dependencies on FusionFix's own injected constants (c209, c222).

And it does not have to be all-or-nothing. A preset replaces **13** shaders, not
1689. The nine containers holding an identified target hold 191 of FusionFix's
1739 shaders, so serving just those from stock keeps **89%** of FusionFix's
shader work — 92.6% if `deferred_lighting.fxc` is left alone, which costs 62
shaders to satisfy two vegetation vertex shaders.

Two hypotheses that sound plausible have been ruled out: FusionFix and ENB do
not collide on shader constant registers, and they do not double-hook D3D9
(FusionFix hooks no device method at all).

An old GTA IV 1.0.4.0 / 1.0.7.0 install is **not** required. It would settle
ENB's hash function outright, but nothing on the critical path depends on that.

Confirmed in game: **ENBSeries 0.163 works on Complete Edition with FusionFix**,
given `API = 0` and Depth of Field set to Low or higher. **iCEnhancer 4 does
not** — its ASI does 1.0.4.0-specific work on the executable and faults during
its own load. [STATUS.md](STATUS.md) has the current picture.

## Conventions

* Every claim says whether it was measured, read out of source, or assumed.
* A shader-map entry marked `confirmed` means a runtime capture showed ENB
  substituting that shader. Nothing else earns that word.
* Failure-log entries get exactly one category. Two categories means two
  entries.
