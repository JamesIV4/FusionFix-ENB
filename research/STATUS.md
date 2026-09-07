# Current status

**Latest user run, September 7 at 11:24: retired build still installed.** The
five screenshots show alternating blue/black sky/building regions, severe
darkening and bright moving-camera edge outlines. The matching 11:23 log reports
`profile=ENBLegacy`, `FusionShaderPackage=1`, `ShaderConstantInjection=1` and
`PostFxBridge=1`; installed ASI is `5df954a5...`. The stock package is
`ced1e28b...`, and neither its cache nor its installation snapshot is present.
This is not runtime validation of the new stock baseline. The staged package,
all 339 original/staged stock files and eleven aliases pass read-only preflight.
Install the current package with the stock setup helper before diagnosing that
baseline. [Screenshots, log and exact hashes](evidence/2026-09-07/user-flicker-old-bridge/report.json).

**September 7: strategy changed to a strict stock CE shader baseline.**
All FusionFix modern shader features and related GPU changes are disabled in
ENB mode. Gameplay, camera and other non-shader fixes remain available. The
modern postfx/depth bridge, extended-tree workaround and modern adapter tools
are removed.

The new stock-only translator produces **eleven aliases for eleven modified
preset inputs**, with unchanged CE grass left alone. All twelve original inputs
are accounted for. Source/preset/target identities are pinned, every unedited CE
instruction is checked byte-for-byte, and six complete translated programs must
exactly match the original assembled preset programs.

The native ASI verifies 339 stock files against compiled-in SHA256 values and
selects them through the loader's file mappings. Old renderer override keys
cannot revive the modern pipeline. The prepared reversible package is
`build/stock-enb-v1`; see [setup](../docs/ENBCompatibility.md) and
[implementation/evidence](stock-ce-strategy.md).

Native build, Python checks, native profile/routing checks and synthetic
installation/restoration pass. No actual game launch, computer use or game-file
changes were performed. Rendering, darkening and artifacts remain unverified.
The next step is a user-run stock-baseline scene; shadows can be evaluated later.

The September 4-6 experiments are historical evidence. Their modern-shader
recommendations and installation commands are superseded by
[the current plan](../GTAIV_FusionFix_ENB_Compatibility_Plan.md).
