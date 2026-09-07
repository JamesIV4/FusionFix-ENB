# Modern shader adapter

**September 6 update:** all translations are implemented. The exact-1.0.4.0
backend produces fifteen aliases covering eleven preset inputs, including both
light-shaft inputs and composite `/10`. Grass needs no preset delta.
See [the completed implementation and test procedure](translations-complete-2026-09-06.md).
The three-terrain backend described below remains a historical reproducible
checkpoint. All twelve identities have been resolved; references below to
four unmapped inputs are superseded.

September 5: the user redirected work from individual visual defects to the
compatibility layer. The FixedBaseline test loaded successfully, but trees were
visually unchanged. Exposure remains unresolved. That result is recorded in
[the run evidence](evidence/2026-09-05/user-fixed-baseline.json).

## Implemented: carry the preset delta into the modern program

`build_shader_adapter.py` is the first modern-shader translation backend.
The existing alias builder routes entire legacy programs to stock CE shaders.
This backend instead starts with FusionFix's program and applies a reviewed
stock-to-iCEnhancer change to it. The resulting alias targets the **modern**
shader identity. The runtime substitution mechanism remains ENB's shaderinput
loader; this does not add a second shader replacement hook to the device.

For all three mapped terrain inputs, the complete preset change is
`def c0.w: 0.25 -> 0`. In both the pinned stock and modern programs this changes
the green addend of `mad oC2.xyz, ..., c0.yyzw, c0.ywyw`. It is a G-buffer channel
change, not an exposure adjustment. The modern code's coverage rejection,
`oC2.w`, stencil output, vertex declarations and logarithmic-depth output stay
intact. This does not establish that ENB's other passes understand those modern
outputs yet.

The builder validates named technique/pass roles, original preset hashes,
stock and modern shader hashes, and the entire preset delta. It assembles both
exports and checks their comment-stripped bytecode against the original blobs.
An independent binary token editor then provides the expected adapted program:
the assembled result must match every token except that one float literal.
It scans the supplied full modern variant for alias collisions before publishing
any output. Unknown deltas are reported without generating replacements.

| Preset input | Modern ENB alias | Status |
|---|---|---|
| psh0CBF49C5 | pshC0223F26 | Assembled and bytecode-checked |
| psh405ABC1B | psh07FE34FB | Assembled and bytecode-checked |
| psh841FD9AE | pshD3E7B05D | Assembled and bytecode-checked |

The [manifest](evidence/2026-09-05/modern-shader-adapter.json) records all eight
mapped inputs, exact deltas, modern interface changes, output identities and
the 103-container collision scan. Five mapped inputs still require custom
adapters; four of the preset's twelve inputs remain unmapped. These numbers are
shader-file coverage, not percentages of a working renderer.

Artifacts are staged in `build/modern-shader-adapter-v2/`. **They require the
matching modern FusionFix pipeline and are not for the current FixedBaseline.**
No modern package or generated alias was installed in the game. Runtime
substitution of these new modern aliases remains untested.

## Next major contract: final composite

The named `GTACompositePostFx/11` role exposes these differences:

| Input | Modern FusionFix | Legacy ENB |
|---|---|---|
| BloomSampler | s4 | s3 |
| AdapLumSampler | s5 | s4 |
| JitterSampler | s6 | s5 |
| StencilCopySampler | s7 | s6 |
| PLAYER_MASK | c86 | c85 |
| GBufferTextureSampler3 | s1, modern depth interpretation | s1, stock depth interpretation |

Modern `BlurSampler` occupies s3 and `NoiseParams` occupies c85. A bridge must
save inputs before relocating overlapping slots, then restore them after its
pass. Copying in stock bytecode alone neither fixes these bindings nor converts
depth. Other composite variants have different layouts: the preset's
`psh22DCDB69` maps to role `/10`, not `/11`, and has ten moved named bindings.

The next implementation target is a legacy interface at the final composite:
shader recognition, named bindings and a compatible depth resource together.
Keep modern world shaders and their paired vertex programs. Establish the
actual inputs and pass order before choosing the resource conversion and
binding hook. The older 1.0.8.0 shader data already supplies the stock contract;
we do not need an old executable address for each shader.

## Implemented: targeted input capture

`TracePostFxInputs` adds read-only snapshots immediately before known composite
draws through DrawPrimitive/DrawIndexedPrimitive. Sixteen pinned diagnostic
identities cover stock and modern slots 12, 13, 15, 17, 19, 25, 27 and 29.
Within the capture window it records at most sixteen snapshots per thread per
frame: texture objects/dimensions/formats at s0..s7/s13, sampler sRGB flags,
constants c44/c66/c72..c86/c209, and render target 0. Every query reports its
HRESULT. Tracing and this option are off by default.

The device is the game-facing boundary. An ENB wrapper may expose cached inputs
and hide its private replacement shaders. These snapshots do not read texture
pixels or prove ENB's internal state. The alias reporter now states that a
missing replacement identity is inconclusive. Shader bind tracking was also
corrected to update only after a successful SetShader call; creation CSV rows
still describe submitted input, not successful creation.

The future user-run `TracePostFx` action starts from FixedBaseline, enables
F10-triggered three-frame capture, and leaves the new modern aliases unstaged.
It preflights fixed artifacts before changing files. When a runtime check is
requested, use this single-line command, launch a normal scene manually, press
F10 once and exit:

```powershell
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-ShaderAliasTest.ps1' -Kit 'C:\temp\enb-revisit\user-test-kit' -Action TracePostFx
```

Then collect the retained logs with:

```powershell
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-ShaderAliasTest.ps1' -Kit 'C:\temp\enb-revisit\user-test-kit' -Action CollectTrace
```

## Validation

All 32 Python tests passed, including literal preservation, comment skipping,
malformed bytecode and changed/ambiguous recipe rejection. All three real
adapters passed D3DX assembly and independent bytecode comparison. The native
Win32 Release build passed with existing conversion/missing-PDB warnings.
New ASI SHA256: `f4d397aa5ed4d2d38e4028bc741814ee583217fd85cf1034b30c3a0dbc57f0a0`.

A synthetic game folder verified TracePostFx configuration, session metadata,
preflight rejection without configuration mutation, and restoration of every
snapshot entry. The sixteen diagnostic hashes were checked against extracted
bytecode. No game was launched or device created for this work; the new runtime
capture and modern shader adapters still need user validation.
