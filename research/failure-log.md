# Failure log

One entry per observed failure, classified once so it is not rediscovered.

Categories: `LOAD`, `HOOK`, `EXECUTABLE`, `SHADER`, `RESOURCE`, `RENDER_STATE`,
`DEPTH`, `POSTPROCESS`, `PROXY_CHAIN`, `FUSIONFIX_FEATURE`, `UNKNOWN`.

Exactly one category per entry. If it seems to need two, it is two entries.

---

## Template

```markdown
### F-000 — <one-line summary>

**Category:** SHADER
**Configuration:** D (CE + FusionFix + iCEnhancer 4.0), API=0, Mode=0
**Scene:** 03 midnight city street
**Expected:** street lighting matches configuration C
**Observed:** scene is black except for emissive surfaces
**First bad frame / pass:** deferred lighting, before the post-process draw
**Relevant shader:** deferred_lighting.fxc #12 (ps)
**Relevant FusionFix feature:** replacement shader package
**Hypothesis:** ENB's shaderinput substitution never fires, so ENB's effect
  operates on a scene it did not modify
**Test performed:** staged the stock shader package, re-ran the scene
**Result:** <what happened>
**Status:** open | explained | fixed | wontfix
```

---

## Entries

### F-001 — ENB effects apply to a scene ENB never modified

**Category:** SHADER
**Configuration:** any configuration with FusionFix's shader package installed
**Scene:** all
**Expected:** ENB's `shaderinput` replacements are compiled in place of the
matching game shaders
**Observed:** not yet observed in-game; predicted from static analysis
**First bad frame / pass:** shader creation, before any frame is drawn
**Relevant shader:** all 103 containers in `update/common/shaders/win32_30`
**Relevant FusionFix feature:** replacement shader package
**Hypothesis:** ENB matches game shaders by a hash of their bytecode. FusionFix
rewrites every shader, so no hash matches and no substitution fires. ENB's
post-process stage still runs, on a scene that lacks the modifications the
preset's effect files assume.
**Test performed:** `tools/shader_dump/compare_sets.py` over the stock CE and
FusionFix shader sets — 1689 compared, 0 identical; of 638 distinct stock
bytecodes, 2 survive. Separately, `match_enb.py` shows the shaders the preset
targets are present in stock CE essentially unchanged (three at similarity
1.000). See [research-log.md](research-log.md), 2026-09-02.
**Result:** the premise is confirmed statically, and the blame is now
attributable: CE preserves these shaders, FusionFix replaces them. The in-game
consequence is not yet confirmed.
**Status:** open — needs configurations C and D run

### F-003 — FusionFix shaders carry no reflection data

**Category:** SHADER
**Configuration:** any configuration with FusionFix's shader package installed
**Scene:** all
**Expected:** shader parameters can be located by name, as in the stock game
**Observed:** 0 of 30 shaders in FusionFix's `rage_postfx.fxc` have a CTAB
constant table, against 28 of 30 in the stock version
**First bad frame / pass:** shader creation
**Relevant shader:** every shader in the FusionFix package
**Relevant FusionFix feature:** the shader build pipeline
**Hypothesis:** RageShaderEditor assembles from `.asm` through
`D3DXAssembleShader`, which emits no reflection data. Anything that resolves a
parameter by name rather than by hard-coded register finds nothing. ENB's
`enbeffect.fx` lists parameter names beside their registers, which suggests it
is one of those things.
**Test performed:** `tools/shader_dump/check_interface.py` against
`research/contracts/enb-postfx.json`.
**Result:** confirmed statically. Whether ENB actually depends on reflection, as
opposed to hard-coded registers, is not established.
**Status:** open

### F-002 — FusionFix content requires a shader only FusionFix ships

**Category:** RESOURCE
**Configuration:** FusionFix installed with `update/common/shaders` deleted
**Scene:** startup
**Expected:** game reaches the main menu with stock shaders
**Observed:** resource error before the main menu (reported in FusionFix issue
#180)
**First bad frame / pass:** content load, before the first frame
**Relevant shader:** `gta_trees_extended` (`.fxc`, `.sps`, `.dcl`)
**Relevant FusionFix feature:** the FusionTrees content package
**Hypothesis:** `update/GTAIV.EFLC.FusionFix` references `gta_trees_extended`,
which exists only in the FusionFix shader package. Deleting the package removes
a shader the content still asks for.
**Test performed:** file-level diff of the stock and FusionFix shader sets —
identical file names except for `gta_trees_extended`, which is FusionFix-only.
**Result:** explains the reported error without needing to reproduce it.
`tools/shader_dump/make_vanilla_package.py` builds a package that keeps this one
shader and takes the other 102 from the stock game.
**Status:** explained — the mitigation is untested in-game
