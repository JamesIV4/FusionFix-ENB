# Steam 1.0.8.0 reference analysis — 2026-09-05

The downloaded depot is a usable **static reference**. Its GTAIV.exe reports
file/product version 1.0.8.0, is 15,628,696 bytes, and has SHA256
`3d90e7c516fa450ca002e5031e62c0f66b404590f33e6cc9793b0da4fffbfd0f`.
Source: app 12210, depot 12211, manifest 4406763129603688303. The user reports
the download finished. No old executable was launched, no content was installed
over CE, and runtime ENB compatibility on 1.0.8.0 has not been tested here.

Reference directory:
`C:\Games\Steam\steamapps\content\app_12210\depot_12211\GTAIV`.

## What is identical to stock CE

Each of the six variant folders contains 102 containers / 1,689 shader blobs.
The comparison yields the same counts in every variant:

| Comparison | Count per variant |
|---|---:|
| Entire containers byte-identical, including metadata/pass state | 94 / 102 |
| Shader blobs byte-identical at the same slot | 1,636 / 1,689 |
| Blobs differing only in comment blocks | 23 |
| Blobs with differences after comment stripping | 30 |
| Added/removed containers or unpaired shader slots | 0 |

Across all variants, 564 of 612 containers are identical. The identical set
includes `rage_postfx`, `deferred_lighting`, `gta_trees`, `gta_grass`, the three
terrain families, `gta_default`, `gta_cutout_fence` and `gta_wire`.
The original timecyc.dat, visualsettings.dat and tree db/dcl files also match CE
byte-for-byte. This compares original paths, not FusionFix's update overrides.

This proves more than the earlier assembly-similarity candidates: the relevant
old/CE container data and interfaces are the same. Copying those 1.0.8.0 files
into CE would therefore change nothing in the current baseline. The missing
extended-tree providers and omitted FusionFix resource gates remain concrete
things to repair; this comparison strengthens that direction.

## What differs

Eight containers differ in each variant:

| Container | Changed program slots after comment stripping, win32_30 |
|---|---|
| gpuptfx_simplerender | 0, 1, 2, 3 |
| gpuptfx_update | 2, 3, 5, 6, 7, 8 |
| rage_atmoscatt_clouds | 0, 1, 2, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16 |
| rage_bink | none; comments/metadata |
| rage_perlinnoise | 1, 2 |
| rmptfx_collision | 1 |
| rmptfx_default | none; comments/metadata |
| rmptfx_litsprite | 0, 2, 3 |

Offline disassembly of rage_atmoscatt_clouds slots 0 and 8 shows compiler stamps
9.26.952.2844 versus 9.29.952.3111, local constant-register changes, scheduling
changes and commuted multiply operands. That is consistent with recompilation,
but does not prove semantic equivalence for every differing program. These
files are now available for targeted sky/particle/noise comparisons if a failing
pass points to them. No blanket old-shader overlay was created.

## ENB hashes and executable patterns

The actual ENB 0.163 hash scan finds **zero matches for the twelve original
iCEnhancer shaderinput filenames in 1.0.8.0**, exactly as in stock CE. The four
ordinary ENB shaderinput filenames are a subset of those twelve. Stock postfx
#13 matches recognized hash AA1C0C36 in four variants; #29 remains 2D5D52B3.
The corresponding CE terrain filenames therefore apply to this old shader set
as well. This does not turn the old preset hash into the CE hash or establish
that every ENB feature supports 1.0.8.0.

The historical FusionFix scanner now finds six of its eight patterns:

| Pattern | 1.0.8.0 pattern-start RVA |
|---|---|
| CreatePixelShader experiment | 0x00009CB3 |
| SetPixelShader experiment | 0x0000B78C |
| SetVertexShaderConstantF | 0x000178A7 |
| SetPixelShaderConstantF | 0x00017607 |
| CreateTexture 1.0.8.0 path | 0x000105FC |
| Shader-folder fallback path | 0x006C4DE8 |

The first two hooks were commented out in the historical source; matching their
patterns does not change that fact. These are observed instruction-pattern
sites, not automatically safe hook targets or CE addresses. The 1.0.7.0 texture
pattern and CE shader-folder pattern do not match the old executable.

The original renderer format immediates agree with CE:

| Purpose | 1.0.8.0 RVA | CE RVA | Both original values |
|---|---|---|---|
| Shadow atlas | 0x006C4C33 | 0x0071D260 | enum 3, R16F |
| G-buffer format selection | 0x00695D24 | 0x006D15C2 | enum 5, A2R10G10B10 |

These support the restored stock values in FixedBaseline. They describe static
code choices, not actual texture creation under a live ENB run.

## Evidence and next step

The reference gives us original shader bytes, renderer instruction sites and
lighting inputs for controlled analysis. It is not a new solution to install.
Continue the repaired baseline's user validation, then target the actual failing
draw/resource boundary. A separately prepared 1.0.8.0 runtime reference could
later distinguish stock CE behavior from executable-version effects; its needed
language/installers and runtime dependencies have not been validated here.

* [Reference metadata](evidence/2026-09-05/steam1080-reference.json)
* [Complete shader comparison](evidence/2026-09-05/steam1080-ce-comparison.json)
* [ENB hash scan](evidence/2026-09-05/steam1080-enb-hashes.json)
* [Historical hook-pattern matches](evidence/2026-09-05/steam1080-hook-patterns.json)

Reproduce without launching the game:

```powershell
python tools/shader_dump/compare_depot_shaders.py '<legacy GTAIV>' '<CE GTAIV>' --out '<new comparison.json>'
python tools/shader_dump/map_enb163.py '<legacy GTAIV>/common/shaders' --preset '<iCEnhancer>/shaderinput' --out '<new hashes.json>'
python tools/shader_dump/map_hook_patterns.py '<legacy GTAIV>/GTAIV.exe' research/contracts/legacy-hooks.json --out '<new patterns.json>'
```
