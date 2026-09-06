# 1.0.4.0 shader reference recovered

September 5, 2026: an archived 1.0.4.0 update contains exact matches for **all
twelve** supplied iCEnhancer shaderinput filenames. This supersedes the four
unresolved identities in the earlier similarity-based map. Shader identity is
established; compatibility of every replacement with CE is not.

The archive came from [The GTA Place's patch listing](https://thegtaplace.com/downloads/f4249-gta-iv-pc-patch-v1040),
using its `/downloads/get/4249` link. The saved `build/GTAIV_Patch_1040.zip` is
actually a RAR container, 56,920,861 bytes, SHA256
`1f6212b85717208d2a5cb1b3186259eb18f2f5622194270a3781a8e7b89da9df`.
It contains `GTAIV_MAINTENANCE_UPDATE_1040_EFIGS.exe`, 57,370,910 bytes, MD5
`b876f90ee674ac40b2ada6799cccb30f`, matching the file checksum on
[the independent archive listing](https://www.ausgamers.com/files/download/45002/grand-theft-auto-4-patch-v1040).

7-Zip extracted the NSIS archive without running its installer. The extracted
GTAIV.exe reports version **1.0.4.0**, SHA256
`9b97e454eb445e6467a70c1867c532e4de328d1dc35b2261ff35f669eb409873`.
The patch includes 89 win32_30 containers; it is a patch reference, not a full
retail game installation. Across its shader variants, 9,316 blobs were scanned,
with all twelve preset names matched and sixteen recognized postfx hashes.
See [the exact hash scan](evidence/2026-09-05/patch1040-enb-hashes.json).

## Named-pass mapping to CE

RageShaderEditor exports of twelve containers are under
`build/legacy1040-exports/{old,ce,modern}`. The old set uses `win32_30_nv8`, which
matches both supplied vertex shaders as well as the pixel shaders.

| Original preset hash | Original container / slot | Named role | CE slot / alias |
|---|---|---|---|
| 0CBF49C5 | gta_terrain_va_2lyr / 5 | deferred_draw | 5 / A5F4E880 |
| 405ABC1B | gta_terrain_va_3lyr / 7 | deferred_draw | 7 / FDFF185D |
| 841FD9AE | gta_terrain_va_4lyr / 9 | deferred_draw | 9 / 1D661524 |
| 54F25463 (VS) | deferred_lighting / 7 | lightShafts 0,1,4,5 | 7 / 9EC48C3F |
| C35A5E05 (VS) | deferred_lighting / 8 | lightShafts 2,3,6,7 | 8 / F40198F6 |
| 22DCDB69 | rage_postfx / 12 | GTACompositePostFx/10 | 12 / 3185A5E0 |
| 71CC11CF | gta_grass / 2 | deferred and deferredalphaclip | 2 / 227985B3 |
| 2DF967C6 | gta_default, gta_cutout_fence / 14 | deferredalphaclip | 15 / B3377693 |
| 323E9BB8 | gta_default, gta_cutout_fence / 13 | deferred_draw | 14 / 12A8C432 |
| F5256B40 | gta_spec / 13 | deferred_draw | 14 / 216B7814 |
| 8DB4CDB2 | gta_normal_spec / 13 | deferred_draw | 14 / 573DE346 |
| 46A43A9F | rage_billboard_nobump / 4 | wd_draw | 4 / 18B040CA |

`2DF967C6` also occurs at old gta_wire slots 13 and 14. Their named CE targets
are 14 and 15 respectively, both carrying the same B3377693 identity. The
lightShafts vertex shaders were previously mislabeled as vegetation wind;
`shader-map.json` now corrects those descriptions.

## Why four newly identified files still need translation

The first three previously unresolved surface shaders target CE passes that
**removed StippleTexture s10 and the corresponding pixel-position declaration**.
Their other named bindings remain compatible. Blind filename aliases would
make the old program sample a texture the CE pass no longer supplies. A
procedural coverage implementation, or an explicitly supplied matching texture,
is needed. Modern FusionFix already has procedural coverage code to study.

The billboard `wd_draw` change is larger. Its old VS supplies color and several
texture-coordinate outputs. CE supplies one packed TEXCOORD0 instead and its
pixel shader outputs depth moments rather than the old sampled color. Both
vertex programs name `gShadowMatrix`; this is a shadow pass. The iCEnhancer
change doubles the old wind scale and changes its offset coefficient. Port that
delta while retaining the current shadow output contract; do not transplant
the old pixel program unchanged.

No files from this patch were installed over the game, and its executable and
installer were never launched.
