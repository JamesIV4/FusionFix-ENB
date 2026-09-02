# gamesetup

Everything needed to put an ENB compatibility test into a GTA IV install, and
take it out again. Nothing here is required to build FusionFix; it exists so a
test configuration is reproducible rather than something assembled by hand and
half-remembered afterwards.

| File | Does |
|---|---|
| `install.ps1` | backs up, installs a preset + this repo's build, appends the ini section, stages the shader overlay, copies the helpers in |
| `ENBCompatibility.ini` | the `[ENBCompatibility]` section `install.ps1` appends, with every setting documented |
| `ENBCompat-Restore.cmd` | undoes all of it from the backup |
| `ENBCompat-Mode.cmd` | switches between test configurations B / C / D |
| `ENBCompat-Preset.cmd` | switches which ENB preset is installed |
| `ENBCompat-Mix.cmd` | bisects a preset one component at a time against a known-good base |
| `ENBCompat-Probe.cmd` | applies/removes the visual shader probes |

## Installing

```powershell
.\install.ps1 -Game "C:\...\Grand Theft Auto IV\GTAIV" `
              -Preset "C:\temp\enbseries_gta4_v0163\Wrapper version"
```

Add `-Selective` to keep most of FusionFix's shaders instead of running entirely
on stock ones.

It refuses to run if `_ENBCompat_Backup` already exists, so a second run cannot
overwrite the record of the original install. Undo with `ENBCompat-Restore.cmd`
in the game folder.

Two things it cannot do for you:

* **`d3d9.cfg` must be `[MAIN] API = 0`.** ENBSeries is a D3D9 wrapper and does
  nothing at all on the Vulkan path.
* **Depth of Field must be Low or higher** in the graphics menu. Off and
  Cutscenes Only make the game bind a post-process pass no preset carries a
  replacement for, and the result is a washed-out image with nothing to say why.
  See [../../research/research-log.md](../../research/research-log.md).

## The helper scripts

They work by renaming files and folders to and from a `.off` suffix, so
switching is instant and survives being interrupted.

`ENBCompat-Mode.cmd`:

| | |
|---|---|
| `C` | ENB only, FusionFix disabled — does the preset work on Complete Edition at all |
| `D` | ENB + FusionFix in ENB mode — the configuration being built |
| `B` | FusionFix only, ENB disabled — check nothing else broke |

The shader package is switched along with the `.asi`, because the game reads
`update\` natively: leaving it in place would feed FusionFix's shaders to a
configuration meant to be running stock ones.

`ENBCompat-Mix.cmd` bisects a preset (`base` / `shaders` / `effect` / `fx` /
`all`), rebuilding from the known-good baseline each time so a run never
inherits leftovers from the previous one.

## Presets

`install.ps1` takes any preset laid out like an ENBSeries download's "Wrapper
version" folder: loose `enb*.fx`/`enbseries.ini`/textures plus a `shaderinput\`
directory.

A preset that ships its own `.asi` needs more care. `ENBCompat-Preset.cmd`
handles the two we tested by snapshotting each into `_ENBCompat_Backup`, and
renames such an `.asi` to `.enbcompat` so the ASI loader ignores it and
`LoadPluginAfterSpoof` decides when it loads.
