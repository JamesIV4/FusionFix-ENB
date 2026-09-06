<#
.SYNOPSIS
User-run, reversible test of the modern FusionFix final-composite adapter.
.DESCRIPTION
Apply enables the modern shader/resource pipeline and the experimental bridge.
IceEffect separately tests the original iCEnhancer main effect on that bridge.
Diagnose applies the bridge and arms three automatic input/output captures.
The four bridge files and the effect have separate snapshots. Restore recovers
both; RestoreEffect only recovers the prior effect. Never launches GTAIV.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Apply', 'Diagnose', 'IceEffect', 'RestoreEffect', 'Restore')][string]$Action,
    [Parameter(Mandatory)][string]$Kit,
    [string]$Game = 'C:\Games\Steam\steamapps\common\Grand Theft Auto IV\GTAIV',
    [string]$Stage = ''
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$gameRoot = (Resolve-Path -LiteralPath $Game).Path.TrimEnd('\')
$kitRoot = (Resolve-Path -LiteralPath $Kit).Path.TrimEnd('\')
if ($kitRoot -eq $gameRoot -or $kitRoot.StartsWith($gameRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Keep the kit outside GTAIV.' }
if (-not (Test-Path -LiteralPath (Join-Path $gameRoot 'GTAIV.exe') -PathType Leaf)) { throw 'GTAIV.exe is missing.' }
if (Get-Process GTAIV -ErrorAction SilentlyContinue) { throw 'Close GTAIV before changing files.' }
$snapshot = Join-Path $kitRoot 'postfx-bridge-snapshot'
$manifestPath = Join-Path $snapshot 'manifest.json'
$relativePaths = @('plugins\GTAIV.EFLC.FusionFix.asi', 'plugins\GTAIV.EFLC.FusionFix.ini',
                   'plugins\ENBCompat\legacy_composite.cso', 'plugins\ENBCompat\legacy_depth.cso')
function Checked-Path([string]$root, [string]$relative) {
    $path = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not $path.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Path escapes root: $relative" }
    return $path
}
function Hash([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
$captureRequest = Checked-Path $gameRoot 'plugins\ENBCompat\capture.request'

$effectSnapshot = Join-Path $kitRoot 'postfx-effect-snapshot'
$effectManifestPath = Join-Path $effectSnapshot 'manifest.json'
$effectTarget = Checked-Path $gameRoot 'enbeffect.fx'
function Restore-Effect {
    $info = Get-Content -LiteralPath $effectManifestPath -Raw | ConvertFrom-Json
    $saved = Checked-Path $effectSnapshot 'enbeffect.fx'
    if ($info.game -ne $gameRoot -or (Hash $saved) -ne $info.sha256) { throw 'Effect snapshot identity/hash mismatch.' }
    Copy-Item -LiteralPath $saved -Destination $effectTarget -Force
    if ((Hash $effectTarget) -ne $info.sha256) { throw 'Effect restoration verification failed.' }
    Write-Host 'Previous main effect restored; bridge configuration retained.'
}
if ($Action -eq 'RestoreEffect') {
    if (-not (Test-Path -LiteralPath $effectManifestPath)) { throw 'No effect snapshot exists.' }
    Restore-Effect
    exit
}
if ($Action -eq 'IceEffect') {
    if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Apply and validate the modern bridge first.' }
    $bridgeInfo = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($bridgeInfo.game -ne $gameRoot) { throw 'Bridge snapshot belongs to another game.' }
    if (-not $Stage) { $Stage = Join-Path $repoRoot 'build\postfx-bridge-v4' }
    $sourceEffect = Join-Path (Resolve-Path -LiteralPath $Stage).Path 'icenhancer_enbeffect.fx'
    $iceHash = 'da7f697611c62dded78ca347965bc60cdd0377d762fb5be96a9b6c36d95f74ee'
    if ((Hash $sourceEffect) -ne $iceHash) { throw 'Staged iCEnhancer effect differs from the inspected original.' }
    $currentIni = Get-Content -LiteralPath (Checked-Path $gameRoot 'plugins\GTAIV.EFLC.FusionFix.ini') -Raw
    $section = [regex]::Match($currentIni, '(?ims)^\[ENBCompatibility\][^\r\n]*\r?\n(?<body>.*?)(?=^\[|\z)')
    if (-not $section.Success) { throw 'Missing ENBCompatibility section.' }
    foreach ($key in @('Mode', 'PostFxBridge', 'FusionShaderPackage', 'ShaderConstantInjection', 'ShadowPipelineFixes')) {
        if ([regex]::Matches($section.Groups['body'].Value, ('(?im)^' + $key + '\s*=\s*1\s*(?://.*)?$')).Count -ne 1) {
            throw "The validated bridge must be active: $key = 1"
        }
    }
    if ([regex]::Matches($section.Groups['body'].Value, '(?im)^ReplacePostFX\s*=\s*0\s*(?://.*)?$').Count -ne 1) {
        throw 'The bridge requires ReplacePostFX = 0.'
    }
    if ((Hash (Checked-Path $gameRoot 'd3d9.dll')) -ne '280e2bc15485bb7b944d47bad9e7d553b6e63eba3afb97bdbc546d45fcc203c4') {
        throw 'The effect test requires the audited ENB 0.163 wrapper.'
    }
    if (-not (Test-Path -LiteralPath $effectManifestPath)) {
        if (Test-Path -LiteralPath $effectSnapshot) { throw 'An incomplete effect snapshot exists; preserve and inspect it.' }
        $originalHash = Hash $effectTarget
        New-Item -ItemType Directory -Path $effectSnapshot | Out-Null
        $saved = Checked-Path $effectSnapshot 'enbeffect.fx'
        Copy-Item -LiteralPath $effectTarget -Destination $saved
        if ((Hash $saved) -ne $originalHash) { throw 'Effect backup verification failed.' }
        [pscustomobject]@{ game = $gameRoot; sha256 = $originalHash } | ConvertTo-Json | Set-Content -LiteralPath $effectManifestPath -Encoding UTF8
    }
    $info = Get-Content -LiteralPath $effectManifestPath -Raw | ConvertFrom-Json
    if ($info.game -ne $gameRoot -or (Hash (Checked-Path $effectSnapshot 'enbeffect.fx')) -ne $info.sha256) { throw 'Effect backup identity/hash mismatch.' }
    Copy-Item -LiteralPath $sourceEffect -Destination $effectTarget -Force
    if ((Hash $effectTarget) -ne $iceHash) { throw 'Effect installation verification failed.' }
    Write-Host 'Original iCEnhancer 4 main effect installed on the existing bridge. Launch through Steam, keep ENB enabled, and compare the same room.'
    Write-Host "Effect-only restore: & '$PSCommandPath' -Kit '$kitRoot' -Game '$gameRoot' -Action RestoreEffect"
    exit
}

if ($Action -in @('Apply', 'Diagnose')) {
    if (-not $Stage) { $Stage = Join-Path $repoRoot 'build\postfx-bridge-v4' }
    $stageRoot = (Resolve-Path -LiteralPath $Stage).Path
    $assets = Get-Content -LiteralPath (Join-Path $stageRoot 'manifest.json') -Raw | ConvertFrom-Json
    $legacy = Join-Path $stageRoot 'legacy_composite.cso'
    $depth = Join-Path $stageRoot 'legacy_depth.cso'
    $asi = Join-Path $repoRoot 'bin\GTAIV.EFLC.FusionFix.asi'
    if (-not (Test-Path -LiteralPath $asi -PathType Leaf)) { throw 'Build the ASI first.' }
    if ((Hash $legacy) -ne $assets.canonical.sha256 -or (Hash $depth) -ne $assets.depth_conversion.sha256) { throw 'Bridge asset hash mismatch.' }
    if ((Hash (Checked-Path $gameRoot 'd3d9.dll')) -ne '280e2bc15485bb7b944d47bad9e7d553b6e63eba3afb97bdbc546d45fcc203c4') { throw 'This test requires the audited ENB 0.163 wrapper.' }
    if ((Hash (Checked-Path $gameRoot 'update\common\shaders\win32_30\rage_postfx.fxc')) -ne $assets.modern_container_sha256) { throw 'The modern postfx container differs from the audited package.' }
    $iniPath = Checked-Path $gameRoot 'plugins\GTAIV.EFLC.FusionFix.ini'
    $text = Get-Content -LiteralPath $iniPath -Raw
    $section = [regex]::Match($text, '(?ims)^\[ENBCompatibility\][^\r\n]*\r?\n(?<body>.*?)(?=^\[|\z)')
    if (-not $section.Success -or [regex]::Matches($text, '(?im)^\[ENBCompatibility\]').Count -ne 1) { throw 'Expected exactly one ENBCompatibility section.' }
    $body = $section.Groups['body'].Value
    $settings = [ordered]@{
        Mode = '1'; PostFxBridge = '1'; FusionShaderPackage = '1'; ShaderConstantInjection = '1';
        ShadowPipelineFixes = '1'; FusionShaderTweaks = '1'; SkyDiffuseSplit = '1';
        ReplacePostFX = '0'; PostProcessAA = '0'; AmbientOcclusion = '0'; SunShafts = '0';
        PreAlphaDepthCopy = '0'; ConsoleGammaBlit = '0'; D3D9Trace = '0'; DumpShaders = '0'; TracePostFxInputs = '0'
    }
    foreach ($key in $settings.Keys) {
        $pattern = '(?im)^' + [regex]::Escape($key) + '\s*=.*$'
        $count = [regex]::Matches($body, $pattern).Count
        if ($count -gt 1) { throw "Duplicate setting: $key" }
        if ($count -eq 1) { $body = [regex]::Replace($body, $pattern, "$key = $($settings[$key])") }
        else { $body += "`n$key = $($settings[$key])`n" }
    }
    $newIni = $text.Substring(0, $section.Groups['body'].Index) + $body + $text.Substring($section.Index + $section.Length)

    if (-not (Test-Path -LiteralPath $manifestPath)) {
        if (Test-Path -LiteralPath $snapshot) { throw 'An incomplete bridge snapshot exists. Preserve and inspect it before retrying.' }
        New-Item -ItemType Directory -Path $snapshot | Out-Null
        $entries = @()
        foreach ($relative in $relativePaths) {
            $target = Checked-Path $gameRoot $relative
            $exists = Test-Path -LiteralPath $target -PathType Leaf
            $sha = $null
            if ($exists) {
                $saved = Checked-Path $snapshot $relative
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $saved) | Out-Null
                Copy-Item -LiteralPath $target -Destination $saved
                $sha = Hash $saved
            } elseif (Test-Path -LiteralPath $target) { throw "Expected a file: $target" }
            $entries += [pscustomobject]@{ path = $relative; existed = $exists; sha256 = $sha }
        }
        [pscustomobject]@{ format = 1; game = $gameRoot; entries = $entries } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    }
}
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'There is no bridge snapshot to restore.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.game -ne $gameRoot -or $manifest.entries.Count -ne $relativePaths.Count -or
    @($manifest.entries.path | Sort-Object -Unique).Count -ne $relativePaths.Count) { throw 'Bridge snapshot does not match this game.' }
foreach ($entry in $manifest.entries) {
    $null = Checked-Path $gameRoot $entry.path
    if ($entry.path -notin $relativePaths) { throw 'Unexpected snapshot entry.' }
    if ($entry.existed -and (Hash (Checked-Path $snapshot $entry.path)) -ne $entry.sha256) { throw 'Bridge backup hash mismatch.' }
}
if ($Action -eq 'Restore') {
    if (Test-Path -LiteralPath $effectManifestPath) { Restore-Effect }
    foreach ($entry in $manifest.entries) {
        $target = Checked-Path $gameRoot $entry.path
        if ($entry.existed) { Copy-Item -LiteralPath (Checked-Path $snapshot $entry.path) -Destination $target -Force }
        elseif (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target }
    }
    if (Test-Path -LiteralPath $captureRequest -PathType Leaf) { Remove-Item -LiteralPath $captureRequest }
    Write-Host 'Pre-bridge files restored. Shader-alias snapshot and logs retained.'
    exit
}
foreach ($pair in @(@($asi, $relativePaths[0]), @($legacy, $relativePaths[2]), @($depth, $relativePaths[3]))) {
    $source, $relative = $pair
    $target = Checked-Path $gameRoot $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force
    if ((Hash $source) -ne (Hash $target)) { throw "Installed hash mismatch: $relative" }
}
[IO.File]::WriteAllText($iniPath, $newIni, [Text.UTF8Encoding]::new($false))
if ($Action -eq 'Diagnose') {
    [IO.File]::WriteAllText($captureRequest, 'postfx-capture-v1', [Text.Encoding]::ASCII)
    Write-Host 'Automatic diagnostics armed. Launch through Steam, keep ENB on and stay in the room for 40 seconds, take a screenshot, then exit.'
    Write-Host 'Three small input/output samples will be saved under GTAIV\ENBCompat\postfx-*. Brief readback pauses are possible. Apply disables further captures.'
} elseif (Test-Path -LiteralPath $captureRequest -PathType Leaf) { Remove-Item -LiteralPath $captureRequest }
Write-Host 'Experimental modern postfx bridge applied; installed ENB preset retained. Launch GTAIV yourself and retain ENBCompat.log after a normal scene.'
Write-Host "Restore command: & '$PSCommandPath' -Kit '$kitRoot' -Game '$gameRoot' -Action Restore"
