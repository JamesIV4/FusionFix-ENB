# Runtime postfx bridge

The experimental implementation is `source/enb_compat/postfxbridge.hxx`. The
existing game composite hook in `source/postfx.ixx` now installs the callback
on ENB's inner device; translation executes at its actual draw boundary. It is opt-in via
`PostFxBridge=1` and requires the full modern shader/constants/shadow pipeline
with FusionFix's replacement postfx chain disabled.

It recognizes modern composite slots 13, 15, 25, 27 and 29; resolves their
current inputs; converts logarithmic depth to stock projection depth; moves
bloom/adaptation/jitter/stencil from s4..s7 to s3..s6; copies PLAYER_MASK from
c86 to c85; then submits a draw with exact stock rage_postfx#13 bytecode. That
bytecode is recognized by ENB 0.163 as AA1C0C36. Unhandled passes retain the
original draw. The current ENB preset remains installed during this test.

The state guard captures resources and render state, restores RT/DS explicitly,
and replays the modified wrapper-facing bindings after applying a state block.
Only c0/c1/c85 are explicitly re-uploaded by restoration. Default-pool resources
are released through the game's device-loss callback and recreated lazily. See
Microsoft's [state-block documentation](https://learn.microsoft.com/en-us/windows/win32/direct3d9/state-blocks-save-and-restore-state)
and [lost-device requirements](https://learn.microsoft.com/en-us/windows/win32/direct3d9/lost-devices).

## ENB's queued constants

Offline decoding showed that ENB's SetPixelShaderConstantF at RVA 28D50 queues
writes, while GetPixelShaderConstantF at 28E70 forwards to the underlying
device. DrawPrimitive at 6990 calls the queue flush helper at 28910 first.
Reading before that flush can see stale values.

`enb163_flush.hxx` calls that private helper at the same draw boundary, after
checking the module-relative GetPixelShader and GetPixelShaderConstantF method
addresses and the helper's executable-memory signature. It does not patch ENB
code. This deliberately couples the adapter to the pinned 0.163 wrapper;
unrecognized implementations fail closed. The initial real TracePostFx capture
reported `enb163_constants_flushed=1` and exposed valid texture dimensions and
projection constants in the indoor scene.

## Runtime observations

The user subsequently authorized game launches and computer use. Shader changes
can require clicking Retry in Rockstar Games Launcher; the initial trace test
did require that retry and then loaded the apartment. Automatic movement was
not reliable, and the user redirected testing to the indoor scene. Movement
automation is paused; it is not a prerequisite for testing this composite pass.

The first modern-bridge run loaded the apartment but produced a darker image
with visible triangular lighting artifacts. The bridge logged an unsupported
composite and retained the original draw. This is **not corrected rendering**.
Evidence: [log](evidence/2026-09-05/modern-bridge-first-run.txt),
[screenshot](evidence/2026-09-05/modern-bridge-first-run.jpg).

A subsequent bounded dump captured a 2,788-byte program, SHA256
`9c95945ec119a268fc1d577593caf5427da2054adbda80f3dcfd0c3832549361`.
It matches modern rage_postfx#13 exactly after stripping comments. Its on-disk
counterpart is 2,880 bytes: the missing 92 bytes are comment metadata. Raw
fingerprint matching therefore rejected the correct program. The adapter now
parses shader tokens and fingerprints all executable tokens while skipping
comments. Malformed/trailing data is rejected. The captured real program passes
the corrected native router test. See
[the diagnostic run log](evidence/2026-09-05/modern-bridge-identity-run.txt).

### GTA IV's command façade: corrected boundary

The following run recognized slot 13 but correctly refused to call the ENB
flush helper through an unexpected device. Read-only live inspection showed
that this device's methods belong to GTAIV.exe (GetPixelShader at RVA 22590,
GetPSConstantF at 22670). The matching getter stubs forward through the pointer
at **+0x11AC**. Its inner device has the expected ENB methods: DrawPrimitive at
6990, GetPixelShader at 11E0 and GetPSConstantF at 28E70. The façade's draw method
records commands in a buffer. Evidence:
[device chain and code prefixes](evidence/2026-09-05/live-modern-device-chain.json).

The new implementation validates both façade getter stubs and the inner ENB
interface before installing a DrawPrimitive callback on the inner vtable.
The game-side hook now only installs this callback and executes the original
game routine. Translation runs during command replay, after queued game state
has reached ENB. A thread-local guard sends the bridge's own conversion/composite
draws to the original method, preventing recursion. The dispatcher preserves
draw arguments and HRESULTs. Unhandled shaders keep the original draw; the
bounded unknown-shader dump is no longer attached to every backend draw.

Device-loss callbacks are registered on the game side during installation,
not from the renderer's replay thread. Installation and diagnostic logging
are synchronized. The latest native tests exercise dispatch fallback,
handled draws, recursive calls, exception cleanup, verified façade getters,
and rejection of changed/null links, in addition to the existing state and
shader-program checks.

## Reproducible checks and test package

37 Python tests pass. The headless native test uses the actual production state
guard with a COM-shaped fake device, checking wrapper-cache restoration, a
failed restore, partial capture and COM reference balance. It also checks five
real modern shaders, metadata variation, mutated-program rejection and the
captured in-game comment-stripped program. No graphics device is created by
that native test.

`prepare_postfx_bridge.py` compiles the depth conversion and extracts the pinned
canonical shader. Current staged assets are in `build/postfx-bridge-v4` (v3's
unchanged bridge assets plus an optional original iCEnhancer main effect); their hashes are
in [the asset manifest](evidence/2026-09-05/postfx-bridge-assets.json).
`Invoke-PostFxBridgeTest.ps1` snapshots four files separately from the original
alias-kit snapshot and enables the modern profile. Apply, incompatible-package
rejection and exact restoration were checked in a synthetic game directory.

```powershell
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-PostFxBridgeTest.ps1' -Kit 'C:\temp\enb-revisit\user-test-kit' -Action Apply
```

Restore the pre-bridge state with the same command and `-Action Restore`.
The original alias-kit restore is separate; do not confuse the two snapshots.

## User result and next check (computer use stopped)

The latest ASI is built in `bin`, SHA256
`5df954a5b28ed2fa615bc4a7e66c8e5f4e7439781275fe44fe1f2c14ef1e2f6f`.
The user installed this build and supplied screenshot 20260905183832_1.jpg.
The installed hash matches. At 18:38:19.552 the backend installed and recognized
slot 13. An initial clip mismatch at .553 was followed by a successful
translated draw at .604. No restore or draw failure was logged. The screenshot
still shows a dark, hazy room and triangular wall artifacts. The deduplicated
log proves that the path ran, but does not measure its frequency or establish
texture contents. Evidence: [run metadata](evidence/2026-09-05/user-bridge-draw.json),
[screenshot](evidence/2026-09-05/user-bridge-draw.jpg),
[log](evidence/2026-09-05/user-bridge-draw.txt).

The user then supplied ENB-on (19:03:55) and ENB-off (19:04:01) screenshots,
reporting improved world seams/normals. The earlier sharp wall splits are much
less apparent in this pair. ENB-on still adds a dark gray veil; ENB-off is
clearer. This improves the visual evidence but does not establish every
material's normal encoding or the full renderer. The toggle leaves the wrapper
and its resource-creation changes in place. See
[the pair's evidence](evidence/2026-09-05/user-enb-toggle.json).

## Original iCEnhancer main effect test

The tested file was still ENB 0.163's original enbeffect.fx (SHA256 5676D639...).
With the bridge now reaching the translated draw, test the actual target effect.
`prepare_postfx_bridge.py --effect <original iCEnhancer enbeffect.fx>` stages the
unchanged, previously inspected compiled effect. SHA256 is pinned to
`da7f697611c62dded78ca347965bc60cdd0377d762fb5be96a9b6c36d95f74ee`.

With GTA IV closed:

```powershell
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-PostFxBridgeTest.ps1' -Kit 'C:\temp\enb-revisit\user-test-kit' -Action IceEffect
```

This action validates the active bridge configuration and ENB wrapper, creates
`postfx-effect-snapshot`, and changes only enbeffect.fx. It does not install the
iCEnhancer ASI, bloom/cloud effects or preset configuration. Launch through Steam
with ENB enabled, wait about ten seconds in the same room, save one screenshot
and exit. `RestoreEffect` restores only the previous main effect. `Restore`
restores both the effect (when its snapshot exists) and the four bridge files.
The original shader-alias kit's snapshot remains separate.

Effect application, effect-only restore, repeated application and combined
restoration passed against a synthetic game folder. The real game has not been
changed by the assistant for this phase; the user runs it.

Full rendering compatibility remains unfinished. The complete preset's remaining material adapters,
visible-artifact fixes and final outdoor coverage also remain required.

## Automatic measurement of the dark output

The user ran IceEffect and supplied 20260905193951_1.jpg. The unchanged original
compiled effect is installed; the room is almost black while HUD remains visible.
The same bridge build logs a translated draw at 19:39:42.516.
[Screenshot, hashes and log](evidence/2026-09-05/user-ice-effect.json).
This is an unresolved rendering failure, not a successful iCEnhancer validation.

The new diagnostic ASI is
`aa316ce1d01296e7ae738930d286ed9ee4dd0b617c5a55f871d5d768d60b3238`.
With GTA IV closed, the user runs:

```powershell
& 'S:\Repos\FusionFix-ENB\tools\gamesetup\Invoke-PostFxBridgeTest.ps1' -Kit 'C:\temp\enb-revisit\user-test-kit' -Action Diagnose
```

Launch through Steam, retry a startup failure as usual, keep ENB enabled, remain
in the room for 40 seconds, save a screenshot and exit. No movement or hotkey is
required. `Diagnose` applies the current bridge and writes
`plugins/ENBCompat/capture.request`; it preserves the effect and preset. The
request survives startup retries. Ordinary `Apply` or `Restore` removes it.

After the first eligible backend draw, snapshots are taken at 5, 15 and 30
seconds, then stop for that process. Each run has its own
`GTAIV/ENBCompat/postfx-<date>-<time>-<pid>` directory. Inputs include c44, c66,
c72..86, c199 and c209; modern s0 G-buffer, s1 log-depth, s2 HDR, s4 bloom,
s5 adaptation and s7 stencil; output includes converted depth and the original
render target immediately after ENB returns. The latter is the composite
boundary, not a claim that all later presentation passes were captured.

Samples preserve raw bits on a centered grid of at most 64 x 36 texels. They
are not averaged screenshots or full texture dumps. Readback copies matching
non-MSAA render targets into system memory, following the documented
[GetRenderTargetData requirements](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-getrendertargetdata).
Unsupported textures and copy failures are logged without adding conversion
draws. Only this explicit diagnostic performs readback; it may briefly stall.
Exceptions remain local to diagnostics and do not suppress the game draw.

Offline analysis:

```powershell
python tools/shader_dump/read_postfx_capture.py '<capture directory>' --out build/postfx-measurements.json
```

Release build, 42 Python tests, headless native state/router/readback tests and
synthetic Diagnose/Apply/Restore checks pass. GPU capture and the actual values
are awaiting the user-run test. The original effect's HDR/adaptation scale and
its use of game parameters are leads; no darkening cause is yet established.
