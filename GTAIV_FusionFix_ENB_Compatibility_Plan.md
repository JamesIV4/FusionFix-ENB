# GTA IV Complete Edition + FusionFix ENB Compatibility Project Plan

GTA 4's local install location on this PC: `C:\Games\Steam\steamapps\common\Grand Theft Auto IV`
ENB location: `ENB resources\enbseries_gta4_v0163.zip`
END shader to use: `ENB resources\icenhancer40.zip`

## Mission

Investigate and implement a compatibility path that allows one or more older GTA IV ENB presets/binaries to run correctly on the current **Grand Theft Auto IV: Complete Edition (1.2.0.59)** together with a modern **FusionFix** build, while preserving as much FusionFix functionality as possible.

The preferred implementation strategy is **not** to modify ENB itself. ENBSeries is closed-source. Instead, treat the problem as an environment-compatibility project:

> Make current GTA IV + FusionFix present the rendering behavior, shader interfaces, hook order, and resources that the target ENB expects.

The ideal end result is an **ENB Compatibility Mode / ENB-compatible FusionFix fork** rather than an ENB rewrite.

---

# 1. Current Understanding


## 1.1 What is probably *not* the main problem

Do **not** start from the assumption that GTA IV Complete Edition contains a universal "disable mods" mechanism.

Complete Edition changed:
- the executable;
- memory layout and code addresses;
- Games for Windows Live / launcher integration;
- parts of the rendering pipeline;
- shaders and shader packaging;
- archive/content behavior;
- mod-loading expectations.

This broke many old mods because they relied on exact executable offsets, old ScriptHook behavior, old shaders, or direct replacement of game assets.

Modern FusionFix demonstrates that extensive modding is still possible on Complete Edition.

---

## 1.2 Why ENB is special

ENB is not just an ASI mod.

For GTA IV it commonly participates in the Direct3D 9 path through a `d3d9.dll` wrapper/proxy and may:
- intercept D3D9 device calls;
- identify shaders;
- inspect or alter render states;
- replace or augment post-processing;
- use scene/depth/render-target resources;
- expect particular shader layouts and constants;
- depend on behavior associated with older GTA IV patches.

Therefore there are at least four independent compatibility dimensions:

1. **DLL/proxy load order**
2. **D3D9 hook compatibility**
3. **GTA IV executable/runtime assumptions**
4. **Shader/resource/render-state compatibility**

Do not collapse these into a single "ENB does not support Complete Edition" diagnosis.

---

# 2. Key Evidence

A historical FusionFix issue is especially important:

**FusionFix issue #180 — "Document ENB compatibility"**

Reported behavior on GTA IV 1.2.0.59:
- ENB + FusionFix causes broken shaders;
- nights become black;
- daytime shaders are wrong;
- deleting `update/common/shaders` alone causes a resource error before the main menu;
- additionally deleting `update/GTAIV.EFLC.FusionFix` makes most things appear to work, though FusionFix functionality is lost.

This is strong evidence that:

> ENB can execute on Complete Edition to a meaningful degree, and at least a major portion of the incompatibility lies in FusionFix shader/update content rather than an absolute inability of ENB to run.

Reference:
https://github.com/ThirteenAG/GTAIV.EFLC.FusionFix/issues/180

Current FusionFix repository:
https://github.com/ThirteenAG/GTAIV.EFLC.FusionFix

Current FusionFix releases:
https://github.com/ThirteenAG/GTAIV.EFLC.FusionFix/releases

ENB proxy documentation:
https://enbdev.com/doc_proxy_en.htm

At the time this plan was written, GitHub lists **FusionFix 5.0.1** as the latest release.

---

# 3. Core Hypothesis

The most promising path is:

```text
Old ENB binary
      |
      | expects old GTA IV rendering behavior
      v
Compatibility layer / FusionFix ENB mode
      |
      | translates, preserves, or emulates expectations
      v
GTA IV Complete Edition 1.2.0.59
```

Instead of:

```text
Modify closed-source ENB
```

prefer:

```text
Modify open-source FusionFix + shaders
```

to behave in an ENB-compatible way.

---

# 4. Important Constraint: ENB is Closed Source

Do not plan around recompiling or directly porting ENB.

FusionFix source can reveal:
- current GTA IV hook locations;
- current executable patterns;
- modern renderer behavior;
- shader replacement mechanisms;
- feature-specific changes;
- old-versus-new GTA IV rendering fixes.

However, it cannot directly reveal what a specific ENB binary internally expects.

That portion must be inferred through:
- controlled experiments;
- logging;
- D3D9 interception;
- shader/resource tracing;
- binary inspection if necessary;
- comparison against an old GTA IV version where the ENB works correctly.

---

# 5. Recommended Target

Start with **one known ENB** and **one known-good old GTA IV patch**.

Suggested structure:

```text
REFERENCE:
GTA IV 1.0.4.0 or 1.0.7.0
+ target ENB
+ minimal unrelated mods

TARGET:
GTA IV Complete Edition 1.2.0.59
+ current FusionFix fork
+ same ENB
```

Do **not** initially attempt generic compatibility with every ENB.

Choose one target ENB whose behavior is well documented and which works reliably on the reference version.

Possible candidates:
- iCEnhancer family;
- IceEnhancer 3.x;
- another classic ENB with a known working 1.0.4.0/1.0.7.0 setup.

The first milestone is proving the architecture on one ENB.

---

# 6. Repository Reconnaissance

Clone FusionFix and document the following before changing code.

## 6.1 Locate

Find all code related to:

- D3D9 device creation;
- `Direct3DCreate9`;
- `CreateDevice`;
- `Present`;
- `Reset`;
- `CreatePixelShader`;
- `CreateVertexShader`;
- `SetPixelShader`;
- `SetVertexShader`;
- render-target creation;
- depth-stencil access;
- texture creation/binding;
- shader replacement;
- shader hashing or identification;
- injected `d3d9.dll`;
- Vulkan/DXVK support;
- ASI initialization;
- pattern scanning / executable hooks;
- shader archive/update loading;
- timecycle/post-processing changes;
- tone mapping;
- shadow pipeline changes;
- AA-related rendering;
- depth-buffer changes;
- deferred/forward rendering alterations, if any.

## 6.2 Build a feature map

Create an internal table:

| FusionFix feature | Source file | Shader dependency | D3D hook dependency | Game hook dependency | Likely ENB conflict |
|---|---|---:|---:|---:|---:|
| Example | `...` | Yes | No | Yes | High |

Populate it systematically.

The goal is to separate:
- gameplay-only fixes;
- UI fixes;
- timing fixes;
- renderer-independent fixes;
- shader-sensitive graphics fixes.

This matters because an ENB mode should retain everything that does not actually conflict.

---

# 7. Establish a Reproducible Test Matrix

Create clean installations or reproducible mod profiles.

Minimum configurations:

### A. Baseline modern game

```text
CE 1.2.0.59
```

### B. Modern FusionFix

```text
CE
+ FusionFix
```

### C. ENB without FusionFix

```text
CE
+ target ENB
```

### D. Conflict reproduction

```text
CE
+ FusionFix
+ target ENB
```

### E. Historical reference

```text
Old GTA IV patch
+ target ENB
```

### F. Historical reference without ENB

```text
Old GTA IV patch
```

Capture the same scenes under all configurations.

---

# 8. Standard Test Scenes

Use deterministic save locations/time/weather where possible.

At minimum capture:

1. Bright daytime exterior
2. Sunset
3. Midnight city street
4. Rain
5. Interior
6. Vehicle paint/reflections
7. Water
8. Shadow-heavy scene
9. Vegetation
10. Artificial light sources
11. Cutscene
12. Pause/menu transition

For each test scene record:

- screenshot;
- FPS;
- crash/no crash;
- ENB effect toggle comparison;
- shaders active;
- render targets;
- major render states;
- whether FusionFix replacement shader was active.

Use consistent resolution/settings.

---

# 9. Phase 1 — Determine What Already Works

Before writing compatibility code, answer:

## Question 1

Does the target ENB initialize on naked Complete Edition 1.2.0.59?

Check:
- ENB startup messages/log;
- effect toggle;
- post-processing;
- bloom;
- adaptation;
- AO;
- depth effects;
- screenshots;
- crash behavior.

If yes, this is extremely important.

It means the first version of this project may primarily require **FusionFix conflict resolution**, not complete ENB-to-CE translation.

---

## Question 2

Which FusionFix files/features trigger failure?

Repeat the issue #180 experiment more systematically.

Do not randomly delete everything.

Disable categories one at a time:

```text
FusionFix ASI logic
FusionFix update package
FusionFix shaders
FusionFix textures
FusionFix D3D wrapper
FusionFix Vulkan wrapper
individual graphics fixes
```

Record the exact transition:

```text
working -> broken
```

for each feature.

---

# 10. Phase 2 — Instrument D3D9

Build a diagnostic D3D9 compatibility layer or temporary logging build.

Instrument at minimum:

```cpp
IDirect3D9::CreateDevice

IDirect3DDevice9::CreatePixelShader
IDirect3DDevice9::CreateVertexShader

IDirect3DDevice9::SetPixelShader
IDirect3DDevice9::SetVertexShader

IDirect3DDevice9::SetPixelShaderConstantF
IDirect3DDevice9::SetVertexShaderConstantF

IDirect3DDevice9::SetTexture
IDirect3DDevice9::SetRenderTarget
IDirect3DDevice9::SetDepthStencilSurface

IDirect3DDevice9::CreateTexture
IDirect3DDevice9::CreateRenderTarget
IDirect3DDevice9::CreateDepthStencilSurface

IDirect3DDevice9::SetRenderState
IDirect3DDevice9::SetSamplerState

IDirect3DDevice9::Present
IDirect3DDevice9::Reset
```

Do not dump every call indefinitely.

Build structured tracing with:
- frame number;
- shader ID/hash;
- render-target dimensions/format;
- depth target;
- state changes;
- draw phase;
- optional call count.

Add filtering.

---

# 11. Shader Fingerprinting

When a shader is created:

1. capture its bytecode;
2. calculate a stable hash;
3. optionally disassemble it;
4. record stage:
   - vertex;
   - pixel;
5. assign observed use.

Example:

```text
PS hash: CE_92AFE331
Seen during:
- vehicle body pass
- RT0 = 1920x1080 A8R8G8B8
- depth present
- textures 0,1,3
```

Build equivalent fingerprints for:

```text
Old GTA IV without ENB
Old GTA IV with ENB
CE without FusionFix
CE with FusionFix
CE + FusionFix + ENB
```

---

# 12. Build the Shader Equivalence Database

Goal:

```text
Old shader role
      |
      +--> old bytecode/hash
      |
      +--> CE equivalent
      |
      +--> FusionFix replacement equivalent
```

Example schema:

```json
{
  "role": "vehicle_lighting",
  "old": {
    "hash": "...",
    "constants": ["..."],
    "textures": ["..."]
  },
  "ce": {
    "hash": "..."
  },
  "fusionfix": {
    "hash": "..."
  }
}
```

Do not assume two shaders are equivalent solely because they are used in the same scene.

Compare:
- inputs;
- constants;
- samplers;
- outputs;
- render target;
- actual semantics.

---

# 13. Compare a Known-Good ENB Frame to CE

This is one of the highest-value experiments.

For the same scene:

```text
Reference old GTA IV + ENB
```

versus:

```text
CE + ENB
```

versus:

```text
CE + FusionFix + ENB
```

Determine precisely where divergence first appears.

Questions:

- Does the same render pass occur?
- Does ENB see depth?
- Are the same render targets available?
- Are texture slots equivalent?
- Are shader constants laid out differently?
- Does FusionFix replace a shader before ENB observes it?
- Is a state restored differently?
- Is tone mapping happening before/after ENB expects?
- Does ENB expect an intermediate buffer that no longer exists?

---

# 14. Phase 3 — Add `ENBCompatibilityMode`

Once conflicts are identified, add a temporary config switch:

```ini
ENBCompatibilityMode=1
```

Do not automatically detect ENB initially.

Explicit mode is easier to debug.

Design it to conditionally disable or alter only known conflicts.

Pseudo-architecture:

```cpp
if (!Config::ENBCompatibilityMode) {
    ApplyNormalFusionFixRendering();
} else {
    ApplyENBCompatibleRendering();
}
```

---

# 15. Preserve Non-Conflicting FusionFix Features

The project should **not** become:

```text
FusionFix with all graphics fixes disabled
```

That would have little value.

Classify every FusionFix feature:

### Category A — Safe

Retain unchanged.

Examples may include:
- gameplay fixes;
- input fixes;
- menu/UI fixes;
- timing fixes;
- camera fixes;
- memory/streaming fixes.

### Category B — Conditionally safe

Keep if testing proves compatibility.

### Category C — Rendering conflict

Modify for ENB mode.

### Category D — Mutually exclusive

Disable only while ENB mode is active.

Document every disabled feature.

---

# 16. Shader Compatibility Strategies

Attempt these in order from least invasive to most invasive.

## Strategy A — Do not replace an ENB-sensitive shader

If FusionFix replacement causes the conflict:

```cpp
if (ENBCompatibilityMode && shader == ProblemShader)
    useVanillaCEShader();
else
    useFusionFixShader();
```

Test.

---

## Strategy B — Build an ENB-compatible variant of the FusionFix shader

Maintain the FusionFix correction but preserve the interface ENB expects.

For example:
- preserve sampler usage;
- preserve constant register semantics;
- preserve intermediate target format;
- preserve depth behavior;
- preserve expected alpha channels.

Conceptually:

```text
FusionFix corrected math
+
legacy-compatible external interface
```

This is preferable to simply turning off the fix.

---

## Strategy C — Recreate old shader semantics

If ENB depends specifically on the old pre-1.0.6.0 shader interface:

```text
CE game state
      |
      v
compatibility shader
      |
      v
old-style shader outputs/resources
      |
      v
ENB
```

FusionFix's existing work restoring older GTA IV graphics behavior may provide useful precedent.

---

## Strategy D — Resource translation

If ENB expects:
- another render target;
- another format;
- depth in another form;
- a particular texture slot;

create or expose an equivalent resource.

Avoid unnecessary copies until correctness is established.

Optimize later.

---

# 17. Hook Ordering / Proxy Chain Investigation

Several components may want to participate in D3D9:

```text
ENB
FusionFix
DXVK
ReShade
other wrappers
```

You must establish a deterministic architecture.

ENB officially supports loading another library through:

```ini
[PROXY]
EnableProxyLibrary=true
InitProxyFunctions=true
ProxyLibrary=other_d3d9.dll
```

But ENB documentation warns some wrappers are not compatible when indirectly loaded.

Test permutations deliberately.

Example candidates:

```text
A:
GTAIV.exe
 -> ENB d3d9.dll
 -> FusionFix compatibility proxy
 -> native D3D9
```

```text
B:
GTAIV.exe
 -> FusionFix proxy
 -> ENB proxy
 -> native D3D9
```

```text
C:
GTAIV.exe
 -> ENB
 -> DXVK
 -> Vulkan
```

```text
D:
GTAIV.exe
 -> FusionFix/compat
 -> ENB
 -> DXVK
```

Do not support DXVK initially unless it already works for free.

First target:

```text
Windows native D3D9
```

Then add DXVK compatibility as a later milestone.

---

# 18. Avoid Double Hooking

Inspect whether both ENB and FusionFix patch/wrap the same D3D9 functions.

Potential failure mode:

```text
ENB hooks Present
FusionFix hooks Present
one stores original pointer
second stores already-hooked pointer
recursive call / bypass / wrong order
```

Create explicit ownership.

Where possible, route calls through a known chain rather than letting two independent hooking libraries race.

---

# 19. Executable Hook Investigation

Only after rendering conflicts are understood, determine whether the ENB binary depends on old GTA IV executable behavior.

Do not assume it does.

If required:

1. identify suspicious ENB reads/writes/calls into `GTAIV.exe`;
2. map those targets on the old executable;
3. determine semantic purpose;
4. find the equivalent current function/data using FusionFix patterns/symbol knowledge;
5. emulate old behavior from the compatibility layer.

Do **not** patch ENB's binary unless absolutely necessary.

Prefer exposing the expected game behavior.

---

# 20. Useful Reverse-Engineering Approach

Use:

```text
Old GTAIV executable
+
FusionFix source knowledge
+
CE executable
```

as a three-way mapping exercise.

For each old behavior:

```text
What did old GTA IV do?
What does CE do now?
How does FusionFix already identify/modify this subsystem?
```

FusionFix's pattern scanning may save substantial reverse-engineering time.

---

# 21. Binary Inspection of ENB

Only do this when experiments show a behavior cannot be explained externally.

Objectives:

- identify imported D3D9 functions;
- identify accesses into GTAIV.exe;
- identify shader hash comparisons;
- identify expected resource formats;
- identify hard-coded game version checks;
- identify initialization failure conditions.

Useful tools:
- Ghidra;
- x64dbg / x32dbg as appropriate;
- API Monitor;
- RenderDoc where compatible;
- PIX/graphics diagnostics if useful;
- custom D3D9 tracing proxy.

Stay focused on interoperability.

Do not attempt to reproduce ENB source wholesale.

---

# 22. Failure Classification

Every failure should go into exactly one category:

```text
LOAD
HOOK
EXECUTABLE
SHADER
RESOURCE
RENDER_STATE
DEPTH
POSTPROCESS
PROXY_CHAIN
FUSIONFIX_FEATURE
UNKNOWN
```

For each bug record:

```text
Configuration:
Scene:
Expected:
Observed:
First bad frame/pass:
Relevant shader:
Relevant FusionFix feature:
Hypothesis:
Test performed:
Result:
```

This will prevent repeatedly rediscovering the same facts.

---

# 23. First Practical Milestone

Target:

> GTA IV CE 1.2.0.59 + current FusionFix fork + one classic ENB loads into gameplay, has correct daytime and nighttime rendering, and can toggle the ENB effect without a crash.

It is acceptable if several FusionFix graphics features are temporarily disabled.

It is **not** acceptable if the solution merely deletes most of FusionFix.

---

# 24. Second Milestone

Restore FusionFix features individually.

For each:

```text
enable feature
run scene matrix
capture differences
classify compatibility
```

Goal:

> Retain all renderer-independent FusionFix fixes and at least the majority of graphical fixes.

---

# 25. Third Milestone

Resolve shader conflicts rather than disabling them.

For each mutually exclusive shader fix:

```text
FusionFix original shader
        |
        v
ENB-compatible FusionFix variant
```

Acceptance:

- visual correction provided by FusionFix remains;
- ENB effect remains correct;
- no black-night bug;
- no incorrect daytime shader;
- no missing render resources.

---

# 26. Fourth Milestone — DXVK

Only after native D3D9 works reliably.

Test:

```text
CE
+ FusionFix ENB fork
+ ENB
+ DXVK
```

Investigate:
- proxy order;
- D3D9 wrapper ownership;
- depth behavior;
- reset/device loss;
- fullscreen/window transitions;
- frame pacing.

Keep DXVK optional.

---

# 27. Fifth Milestone — Generalize Beyond One ENB

Once one ENB works, test additional ENBs.

Do not immediately add per-preset hacks.

Look for common expectations:

```text
ENB A \
ENB B  ---> common old-GTA rendering contract
ENB C /
```

If multiple ENBs fail in the same way, implement the old rendering contract rather than special-casing binaries.

---

# 28. Automatic ENB Detection

Only after the compatibility mode is stable.

Potential signals:
- known ENB module loaded;
- `enbseries.ini`;
- expected exports/module names.

Still allow explicit override.

Example:

```ini
ENBCompatibilityMode=Auto
```

Modes:

```text
0
1
Auto
```

---

# 29. Configuration Design

Potential settings:

```ini
[ENBCompatibility]
Mode=Auto
PreserveLegacyShaderInterfaces=1
DisableConflictingPostFX=1
ExposeLegacyDepth=1
VerboseLogging=0
```

Avoid exposing dozens of obscure toggles publicly.

Internal debug flags are fine.

---

# 30. Performance

Correctness first.

After compatibility works, profile:

- shader swaps;
- render target copies;
- resolve operations;
- depth copies;
- CPU hook overhead;
- state tracking;
- proxy overhead.

Avoid full-frame copies if a shared/compatible resource is possible.

---

# 31. Regression Requirements

FusionFix normal mode must remain unchanged.

CI/manual test:

```text
ENBCompatibilityMode=0
```

should be behaviorally equivalent to upstream FusionFix.

Do not make ENB support the default unless auto-detection is extremely reliable.

---

# 32. Upstream Strategy

Develop in a fork initially.

Keep changes modular:

```text
source/enb_compat/
shaders/enb_compat/
```

or equivalent clean separation.

Avoid scattering:

```cpp
if (enb)
```

across dozens of unrelated files.

Prefer an abstraction such as:

```cpp
RendererCompatibilityProfile
```

with profiles:

```text
FusionFixDefault
ENBLegacy
```

This makes an eventual upstream PR far more realistic.

---

# 33. Recommended Branch Structure

```text
main/upstream
research/d3d9-tracing
research/shader-map
feature/enb-compat-core
feature/enb-shader-compat
feature/enb-dxvk
```

Keep instrumentation separate from production patches where practical.

---

# 34. Instrumentation Deliverables

The investigation should produce reusable tools/data:

```text
/tools
    d3d9_trace/
    shader_dump/
    frame_compare/

/research
    shader-map.json
    feature-conflicts.md
    proxy-chain-results.md
    rendering-pipeline.md
```

These artifacts are almost as valuable as the code.

---

# 35. High-Priority Questions

Answer these first:

1. Does the chosen ENB initialize on bare CE 1.2.0.59?
2. Which exact FusionFix component first causes wrong rendering?
3. Is failure caused by shader *identity*, shader *interface*, or shader *output*?
4. Does ENB need an old depth-buffer representation?
5. Does ENB depend on specific old intermediate render targets?
6. Is hook order deterministic?
7. Does FusionFix's `d3d9.dll` need to exist in ENB mode?
8. Which FusionFix graphics features can remain enabled unchanged?
9. Does ENB inspect GTAIV executable addresses directly?
10. Can the compatibility target be expressed as an old-GTA rendering contract rather than ENB-specific hacks?

---

# 36. Things Not to Do Initially

Do not:

- rewrite ENB;
- attempt universal ENB support;
- add ReShade;
- add DXVK before native D3D9 works;
- optimize early;
- replace half of FusionFix without identifying the conflict;
- blindly copy shaders from GTA IV 1.0.4.0;
- hard-code shader mappings without documenting semantics;
- patch random GTAIV memory offsets;
- assume every visual mismatch is a shader problem.

---

# 37. Likely Architecture

A plausible final design:

```text
GTAIV.exe
    |
    v
D3D9 entry layer
    |
    +--------------------------+
    | FusionFix core hooks     |
    | gameplay/UI/timing fixes |
    +--------------------------+
    |
    v
Renderer compatibility profile
    |
    +------------------+-------------------+
    |                                      |
Default FusionFix                     ENB Legacy
    |                                      |
Fusion shaders                    compatible shaders
modern resources                  legacy interfaces
modern post FX                    adjusted post FX
    |                                      |
    +------------------+-------------------+
                       |
                       v
                    ENB hooks
                       |
                       v
                Native D3D9 / DXVK
```

The exact ENB/FusionFix proxy order must be determined experimentally.

---

# 38. Definition of Success

## Minimum success

```text
CE 1.2.0.59
+ FusionFix fork
+ target classic ENB
```

boots, enters gameplay, renders day/night correctly, and does not require removing most FusionFix content.

## Strong success

- most FusionFix features remain enabled;
- ENB shaders/effects behave like the historical reference;
- native D3D9 is stable;
- compatibility mode is modular;
- no changes to upstream/default mode.

## Excellent success

- multiple old ENBs work;
- DXVK works;
- compatibility is based on generalized old-renderer semantics;
- the patch is clean enough for possible upstream consideration.

---

# 39. Immediate First Tasks for the Implementing AI

Perform these in this order:

### Task 1
Clone and build current FusionFix unmodified.

### Task 2
Identify the exact shader submodule/repository and document how shaders are built, packaged, and loaded.

### Task 3
Reproduce FusionFix issue #180 with the selected ENB.

### Task 4
Verify the same ENB on bare CE without FusionFix.

### Task 5
Binary-search FusionFix files/features until the minimal conflict set is known.

### Task 6
Add temporary logging around FusionFix's shader replacement path.

### Task 7
Dump/hash shaders for:
- CE;
- CE + FusionFix;
- old reference GTA IV.

### Task 8
Identify the first visually incorrect render pass.

### Task 9
Add `ENBCompatibilityMode` and bypass only that conflicting shader/change.

### Task 10
Repeat until day/night baseline rendering is correct.

Only after these tasks should the project expand into deeper executable reverse engineering.

---

# 40. Decision Tree

```text
Does ENB work on bare CE?
        |
   +----+----+
   |         |
  YES        NO
   |         |
   v         v
Focus on     Determine whether failure is
FusionFix    D3D proxy, shader, resource,
conflicts    executable, or version check
   |
   v
Disable smallest conflicting FF feature
   |
   v
Does ENB work?
   |
 +----+----+
 |         |
YES        NO
 |         |
 v         v
Rebuild     instrument D3D9 and compare
feature     old vs CE render pipeline
in ENB-
compatible
form
```

---

# 41. Guiding Principle

Do not think:

> "How do we make ENB understand modern FusionFix?"

Think:

> "What rendering contract does this ENB expect, and how can FusionFix expose that contract while retaining its modern fixes?"

That framing is likely to produce the cleanest and most general solution.

---

# 42. Research Notes / Known Uncertainties

Treat the following as hypotheses until verified:

- ENB may identify GTA IV shaders by compiled bytecode/hash.
- ENB may depend on particular constant-register layouts.
- ENB may depend on old intermediate render targets.
- ENB may access GTAIV.exe memory/functions directly.
- FusionFix and ENB may double-hook the same D3D9 calls.
- Some shader conflicts may be caused by changed resource semantics rather than shader identity.
- Some historical ENBs may already contain Complete Edition-specific modifications.

Do not encode these assumptions into production architecture without evidence.

---

# 43. Useful Output From Every Investigation Session

At the end of each meaningful investigation, append to a research log:

```markdown
## YYYY-MM-DD — Experiment name

### Configuration
...

### Hypothesis
...

### Changes
...

### Observation
...

### Conclusion
...

### Next experiment
...
```

The goal is to leave enough evidence that another developer or AI can continue without repeating the same experiments.

---

# 44. Final Perspective

This project is technically ambitious but unusually plausible because:

1. the ENB binary demonstrably gets far enough on Complete Edition to produce rendered output;
2. known failures correlate strongly with FusionFix shader/update content;
3. FusionFix is open source;
4. FusionFix already contains substantial knowledge about modern GTA IV internals and legacy rendering behavior;
5. compatibility can likely be introduced incrementally rather than requiring a renderer rewrite.

The likely hardest problem is **not merely finding updated GTAIV.exe addresses**.

The hardest problem is discovering and preserving the **rendering contract expected by an older closed-source ENB** while retaining FusionFix's modern rendering corrections.

Solve that contract systematically, and the project has a credible path forward.
