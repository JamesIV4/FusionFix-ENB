# Legacy FusionFix bridge investigation — 2026-09-04

The project is reopened. **iCEnhancer 4 is not yet working in the game**, but
shader obfuscation does not justify stopping: all three bundled effects load,
validate, bind their passes, and disassemble through the ordinary D3DX9 runtime.
The old FusionFix sources also provide a useful *named shader interface* bridge.
Before the user requested manual PC testing, one shaderinput-only game launch
was attempted and exited before scene inspection. The original game files and
settings were restored; all sixteen backed-up file hashes matched afterward.
Since that request, work has been limited to source/files and offline analysis.
Further game or D3D9 runtime tests are for the user to perform.

## What was actually tested

Built `tools/shader_dump/inspect_effect.cpp` with VS 18 / x86, `/W4`, no compiler
warnings. Used the repository's Microsoft D3DX9_43 and the system D3D9 runtime
on a HAL device, with a private window that is never shown. No ENB DLL or
iCEnhancer ASI was loaded. Every `ValidateTechnique`, `Begin`, `BeginPass`,
`EndPass`, and `End` call succeeded. No geometry was drawn.

| Original iCEnhancer file | Bytes | Parameters | Techniques / passes | Shader programs |
|---|---:|---:|---:|---:|
| enbeffect.fx | 15024 | 37 | 1 / 1 | 1 |
| enbbloom.fx | 13544 | 13 | 4 / 4 | 8 |
| enbclouds.fx | 18272 | 4 | 2 / 2 | 3 |

All three start with `01 09 FF FE`, a compiled D3D9 effect signature. Ordinary
`fxc /dumpbin` on the entire effect fails; **D3DXCreateEffectFromFile followed by
D3DXDisassembleEffect succeeds**. Extracting the embedded shader streams and
disassembling them individually also succeeds. The difference between a whole
effect and an individual shader matters here. Microsoft's API explicitly accepts
[text and binary effects](https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dxcreateeffect).

The output retains meaningful names: `Shader_C215BE6E`, `BloomPrePass`,
`BloomTexture1`, `BloomTexture2`, `BloomPostPass`, `Shader_Clouds`, `ShiftClouds`,
`ScreenSize`, `CameraPosition`, `Timer`, the `_cNN` game constants, and texture
parameters. These are usable interfaces, not unreadable encrypted shader code.
Some programs contain **preshaders** (CPU-side effect calculations); extracting
only GPU instruction bodies would lose that behavior. Use the original effect
binary through D3DX rather than assuming a raw shader assembly transplant is equal.

Machine-readable evidence, including input and output SHA-256 hashes:
[icenhancer-effects.json](evidence/2026-09-04/icenhancer-effects.json).
Full local reflection/disassembly artifacts are in
`C:\temp\enb-revisit\verified-{enbeffect,enbbloom,enbclouds}`. The repository
stores metadata and tooling, not redistributed copies of the preset's programs.

This proves these effects can load and bind **without their ASI in an isolated
harness**. It does not prove that ENB initializes them the same way, that the
ASI contributes nothing else, or that their resources contain the correct scene.
The previous two preset-only game failures remain failures needing explanation.

## What the older FusionFix sources provide

Pinned sources inspected, not inferred from a current README alone:

* [Zolika's fork, dc33fad](https://github.com/Zolika1351/GTAIV.EFLC.FusionFix/tree/dc33fad9163fa1aa3c7a85b1210347e2e8bd83c3),
  September 2023: 1.0.7.0/1.0.8.0 renderer hooks, including constant uploads and
  separate CreateTexture paths. Its CreatePixelShader / SetPixelShader experiment
  at `source/dllmain.cpp:1576–1663` is **commented out**. It is not evidence of a
  working shader replacement hook, nor an ENB identity table.
* Its exact shader submodule,
  [9d86139](https://github.com/Parallellines0451/GTAIV.ShaderFixesCollection/tree/9d8613917d492720cd1192372dc16674c49cd6ec),
  explicitly targets 1.0.7.0, 1.0.8.0 and CE. Its build script copies one set of
  compiled fixes to the three variant folders. It provides shader assembly,
  named parameters, register assignments, and named technique/pass relationships.
* [Gillian's GFWL fork, aee995b](https://github.com/gillian-guide/GTAIV.EFLC.FusionFix-GFWL/tree/aee995b0181feea58ed3682417d48a0c125beb06),
  July 2025: unified shader-folder selection and alternative executable patterns.
  Its own `FusionShader` markers identify its shaders, not ENB's original hashes.

The supplied iCEnhancer 4 targets **1.0.4.0**; the historical FusionFix bridge
targets **1.0.7.0/1.0.8.0/CE**. They are related evidence, not the same reference
configuration. No 1.0.4.0 or 1.0.7.0 executable was available or tested here.

The pattern scanner records eight historical patterns against the installed CE
executable, SHA-256
`08759a5516f9837920ea504436236bbab89d0826a8e4d04ff106345177b5345d`.
Only the CE shader-path alternative matches, at **RVA 0x0071D1D7**.
The legacy creation/binding/upload/texture patterns do not match its executable
sections on disk. Absence on disk is not proof of absence from runtime memory.
See [ce-hook-patterns.json](evidence/2026-09-04/ce-hook-patterns.json) and
[legacy-hooks.json](contracts/legacy-hooks.json). No address was patched.

The stable part of these hooks is the D3D9 COM boundary: pixel shader creation,
binding and float constants use vtable indices 106, 107 and 109; vertex constants
use 94, texture creation 23. These are method offsets, **not shader identities**.
The existing ENB tracer already reaches this boundary without old executable
addresses. Building another address-only compatibility layer would duplicate it.

## A concrete shader mapping from the old bundle

`audit_shader_pair.py` joins shaders by **technique name, pass ordinal, and
stage**, then compares named register bindings, declarations, explicit depth
writes and pass state. It reports missing/ambiguous mappings instead of assuming
the nth shader is equivalent across versions. RAGE's vertex references are
zero-based and pixel references are one-based; this is covered by a parser test.

For `rage_postfx.fxc`, the target identified in earlier runtime work maps to
`GTACompositePostFx`, pass ordinal 11, pixel slot 13. In the old shader bundle,
**all twenty stock bindings are preserved**. Modern FusionFix's corresponding
pass moves these five:

| Parameter | Stock CE / historical FusionFix | Modern FusionFix |
|---|---|---|
| BloomSampler | s3 | s4 |
| AdapLumSampler | s4 | s5 |
| JitterSampler | s5 | s6 |
| StencilCopySampler | s6 | s7 |
| PLAYER_MASK | c85 | c86 |

Modern FusionFix additionally binds BlurSampler at s3, NoiseParams at c85,
StippleTexture at s10, and NearFarPlane at c128. This is a concrete starting
point for a pass-specific adapter or a legacy-interface shader variant. It is
not permission to globally remap those slots: unrelated passes use them too.
The old bundle also preserves the source bindings for postfx slots 12 and 29,
cutout-fence slot 15 and wire slot 14. Deferred-lighting slot 8 has a missing
named variable, so even historical metadata must be checked rather than trusted.

Fourteen source/target container audits are recorded in
[shader-role-mapping.json](evidence/2026-09-04/shader-role-mapping.json).
Matching these interfaces is stronger evidence than assembly similarity, but it
does not by itself resolve ENB's hashes or prove image equivalence. The separate
ENB binary investigation below recovered the hash calculation.

## Why simply splicing stock bytecode is insufficient

The previous "a container is the floor" statement was already superseded by
`splice_fxc.py`: all 1689 stock and 1739 FusionFix blobs in the installed
`win32_30` sets have the expected two-u16 size headers. Original bytecode and
CTAB can be preserved without reassembling them. However, keeping FusionFix's
binding tables while inserting stock postfx slot 13 would feed it the wrong
samplers and c85. Bytecode preservation solves identity, not resource semantics.

There is a second, more consequential boundary. Modern FusionFix's terrain
pixel shaders write **oDepth**, using c209 and new vertex interpolants; stock
terrain shaders do not. The vertex stages also carry added depth-related
outputs. The paired RAGE technique's state changes as well. Dropping a stock
pixel shader into those passes can mix different depth encodings. The earlier
claim that retaining 89% of shader blobs means retaining 89% of working graphics
features is unsupported. No experimental package is being presented as a fix.

## ENB's actual hash recovered without running its DLL

`decode_enb163.py` independently translates the supplied wrapper's packing stub
into Python. It accepts only SHA-256
`280e2bc15485bb7b944d47bad9e7d553b6e63eba3afb97bdbc546d45fcc203c4`.
It decodes 1,850,794 bytes, restores 9,936 branch filters and 15,832 relocations.
The result is a non-runnable inspection blob starting at RVA 0x1000, with
unresolved imports. The original DLL is never changed or executed by this tool.
Do not mistake this for a generic unpacker or redistribute the decoded binary.

The recovered pixel creation routine at RVA **0x1230**, and vertex routine at
**0x2400**, scan raw DWORDs for the first `0000FFFF`. They include the version
and comments and **exclude that END word**. The pixel scan limit is 100,000
DWORDs; the vertex limit is 200,000. This is a raw scan, not the semantic token
walker: even a matching DWORD inside a comment ends it early. Both call
**0x226E0**, which cross-checks table and bitwise implementations of reflected
CRC32, polynomial `EDB88320`, initial `FFFFFFFF`, **without final XOR**.

For normal extracted shaders:

```python
enb_hash = zlib.crc32(raw[:first_aligned_END]) ^ 0xffffffff
```

`enb163_hash.py` implements this precisely; `d3d9bc.Shader.hashes()` now exposes
it as `enb163` alongside the existing unrelated CRCs. The live tracer's
`crc32_stripped` remains a different identifier.

At RVA **0x6A1C..0x6A4A**, ENB routes SIX shader hashes into its postfx handler:
`7BC57CE4`, `7D9A776E`, `B2497014`, `C50103F3`, `AA1C0C36`, `C215BE6E`.
The shared call is RVA 0x6A66. **CE stock rage_postfx#13 hashes to AA1C0C36**,
not C215BE6E. The latter names the effect's canonical technique. Stock #29
hashes to `2D5D52B3` and is absent from this recognition chain. This independently
supports the earlier DOF finding and corrects the claim of a single target hash.

Across all six installed stock variants (10,134 extracted shaders), none of the
**twelve original iCEnhancer shaderinput filenames** matches. Four copies of
postfx #13 match AA1C0C36. Modern FusionFix's win32_30 set (1,739 shaders) matches
neither the twelve filenames nor any of these six postfx hashes. These are
on-disk results; runtime changes to submitted shader bytes remain possible.
The earlier broad statement that shaderinput replacement was visually proven
on CE needs rechecking against actual filenames and shader creation inputs.
Postfx rendering and arbitrary shaderinput substitution are distinct paths.

This also corrects "CE did not change the shaders": a matching normalized
instruction body does not mean matching raw bytecode, reflection, or hash.
Evidence: [enb163-identity.json](evidence/2026-09-04/enb163-identity.json).
ENB also imports ordinary `D3DXCreateEffectFromFileA` and calls it for
`enbeffect.fx` (initial load RVA 0x25516, reload 0x242AD). This strengthens the
standard-effect route; successful isolated binding still is not game rendering.

## A staged filename bridge

`make_shader_aliases.py` creates new filenames for selected stock CE candidates.
It preserves the preset assembly bytes, pins both input SHA-256 values, refuses
modern/changed bytecode, checks all affected stock slots for hash collisions,
and writes only to a new directory outside the installed game. It changes no
DLL, executable, shader container, or live configuration.

| iCEnhancer filename hash | Stock CE alias hash | Candidate | Selection |
|---|---|---|---|
| 0CBF49C5 | A5F4E880 | terrain 2-layer #5 | default; combined terrain probe positive |
| 405ABC1B | FDFF185D | terrain 3-layer #7 | default; combined terrain probe positive |
| 841FD9AE | 1D661524 | terrain 4-layer #9 | default; combined terrain probe positive |
| 54F25463 | 9EC48C3F | deferred_lighting vertex #7 | optional candidate |
| C35A5E05 | F40198F6 | deferred_lighting vertex #8 | optional candidate |
| 22DCDB69 | 3185A5E0 | rage_postfx pixel #12 | optional candidate |
| 71CC11CF | 227985B3 | grass pixel #2 | optional candidate |
| 2DF967C6 | B3377693 | cutout/default #15, wire #14 | optional candidate |

The first three have matching normalized instruction bodies and declarations.
On September 4 the user ran all three CE aliases with a magenta diffuse probe;
a terrain strip rendered magenta, with the installed files hash-matching the
staged probe. This confirms the alias mechanism and at least one mapping in the
terrain group at runtime. Because all three were active, it does not independently
confirm each row. See
[the screenshot and run evidence](evidence/2026-09-04/user-terrain-probe.json).
The remaining five rely on weaker static candidate evidence; four unresolved
preset files are excluded entirely. None is labeled a confirmed runtime mapping.
Historical FusionFix helps check the role/interface correspondence; it did not
supply these ENB hashes. The decoded ENB algorithm supplies the CE identifiers.

Staged locally, **not installed**:

* `C:\temp\enb-revisit\ce-terrain-aliases` ? three default aliases.
* `C:\temp\enb-revisit\ce-all-candidate-aliases` ? eight experimental aliases.

Contracts and manifests are checked in; preset assembly remains local:
[ce-shader-aliases.json](contracts/ce-shader-aliases.json),
[terrain manifest](evidence/2026-09-04/ce-terrain-aliases.json),
[all-candidate manifest](evidence/2026-09-04/ce-all-candidate-aliases.json).
These aliases target **stock CE**, not modern FusionFix's changed depth pipeline.

## Reassessment of the ASI crash using existing dumps

Two existing September 2 dumps were available after all: `GTAIV.exe.22832.dmp`
and `GTAIV.exe.56592.dmp`. `inspect_crash.py` reads their x86 exception contexts
and compares captured code with the installed executable. It starts no process.

In the first dump, EIP is game+0x008D6D22, ESI is 0x0037955C, and the fault is a
read at 0x7CAF9FCC. The relevant bytes are:

```text
on disk: 83 BE 70 0A 00 00 01 74 12   cmp [esi+0xA70], 1 ; then je
runtime: 83 BE 70 0A 78 7C C9 06 12   cmp [esi+0x7C780A70], -0x37
```

ESI + the runtime displacement equals the fault address exactly. Four bytes
at game RVAs **0x8D6D26..0x8D6D29** changed, spanning the displacement, immediate
and following branch opcode. No base relocation entry was found at that span.
The second dump faults at the same instruction with different changed bytes.
This is stronger evidence than the earlier guess of a bad object pointer:
**the instruction itself changed in memory**. The dumps do not identify the
writer. An incompatible patch is a hypothesis to test, not an established
attribution to one ASI hook. The iCEnhancer module is present in both dumps.

Sanitized evidence: [first dump](evidence/2026-09-04/asi-crash-22832.json),
[second dump](evidence/2026-09-04/asi-crash-56592.json). Do not redistribute full
crash dumps. If ASI functionality turns out to be needed, a debugger data
breakpoint on that four-byte span before plugin loading is a much narrower next
experiment than guessing a map of the entire old executable.

## Game-test boundary and next user test

The September 4 attempt used ENB 0.163's original effects, twelve iCEnhancer
shaderinput files, stock shader overlay, compatibility ASI, tracing enabled,
and no iCEnhancer ASI. The launcher recorded exit `0xC0000005` before any scene
was inspected. No paired four-file stock baseline was run, so this cannot be
attributed to the replacement files, tracing, or an effect. The new aliases were
created later and have **never been tested in the game**.

All sixteen backed-up installed file hashes and the settings backup were
restored. Test-only additions were moved into scratch. The user subsequently
requested that they perform PC testing, so no further game/native-device tests
were run. All later verification was offline code/data analysis.

Next, the user should follow [the focused test instructions](alias-test.md):

1. Re-establish the previously working ENB 0.163 / stock-shader baseline with
   DOF enabled, **tracing disabled**, and no iCEnhancer ASI or version spoof.
   Stop there if it fails; that is the unresolved baseline failure.
2. Add only the three terrain aliases and compare the same outdoor view.
   This tests whether the recovered filename bridge reaches real game shaders.
3. Separately restore the baseline and replace only `enbeffect.fx` with the
   original iCEnhancer compiled effect. Introduce bloom/clouds and their assets
   one at a time afterward. A failure needs its component and existing log/dump,
   not a conclusion that the shader language is unreadable.
4. Only after the stock path works, adapt modern FusionFix's named sampler and
   constant moves, paired vertex outputs and depth representation per pass.
   The ASI is a separate dependency to diagnose only if behavior requires it.

This is a reproducible shader identity bridge and a narrower crash diagnosis,
not a completed iCEnhancer port.


## User follow-up: baseline renders (September 4, 21:00 screenshot)

The user ran the prepared Baseline and reported successful outdoor scene loading,
with strong over-brightening similar to the earlier ENB result. Screenshot
`20260904210046_1.jpg` shows the Hove Beach street under elevated tracks, with
washed-out shadows, cyan cast and clipped-looking highlights. This does not
establish whether brightness is a tuning issue or incorrect postfx inputs.

Read-only comparisons confirm the installed ENB DLL, effect, ENB ini and
FusionFix ini match the staged baseline. The log confirms stock nv8 shaders,
ENBLegacy with renderer flags off, and no version spoof. DepthOfField is 9 in
the persisted FusionFix config. Only the four original ENB shaderinput files
are installed. The user-created snapshot is present. Evidence:
[user-baseline.json](evidence/2026-09-04/user-baseline.json).

The earlier startup crash remains unattributed, but it is not reproduced by
this baseline. The next user test is the magenta terrain probe on blended
dirt/grass ground. Brightness remains unchanged so that comparison isolates the
new shader filenames. Neither alias substitution nor iCEnhancer postfx rendering
is proved by the successful baseline alone.
