<#
.SYNOPSIS
User-run, reversible installation of the reviewed modern iCEnhancer shader adapters.
.DESCRIPTION
Requires the exact full modern shader variant and active postfx bridge. Changes
only the generated shaderinput aliases; preserves the first pre-test snapshot.
An expanded stage adds backups for its new aliases without replacing old ones.
All source files and backups are checked before writes. Never launches GTAIV.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Apply', 'Restore')][string]$Action,
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
function Checked-Path([string]$root, [string]$relative) {
    $path = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not $path.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Path escapes root: $relative" }
    return $path
}
function Hash([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
$snapshot = Checked-Path $kitRoot 'modern-material-snapshot'
$snapshotManifest = Join-Path $snapshot 'manifest.json'
$aliases = @{}
if ($Action -eq 'Apply') {
    if (-not $Stage) { $Stage = Join-Path $repoRoot 'build\modern-preset-adapters-v4' }
    $stageRoot = (Resolve-Path -LiteralPath $Stage).Path.TrimEnd('\')
    $assets = Get-Content -LiteralPath (Join-Path $stageRoot 'manifest.json') -Raw | ConvertFrom-Json
    if ($assets.format -ne 1 -or $assets.backend -ne 'exact_1040_reviewed_delta') { throw 'Unsupported material manifest.' }
    foreach ($entry in $assets.entries) {
        if ($entry.status -ne 'built_offline') { continue }
        foreach ($target in $entry.targets) {
            if ($target.alias -cnotmatch '^[pv]sh[0-9A-F]{8}\.txt$') { throw 'Invalid alias filename.' }
            if ($aliases.ContainsKey($target.alias) -and $aliases[$target.alias] -ne $target.assembly_sha256) { throw 'Conflicting material aliases.' }
            $aliases[$target.alias] = $target.assembly_sha256
            $source = Checked-Path $stageRoot ('shaderinput\' + $target.alias)
            $binary = Checked-Path $stageRoot ('assembled\' + [IO.Path]::GetFileNameWithoutExtension($target.alias) + '.cso')
            if ((Hash $source) -ne $target.assembly_sha256 -or (Hash $binary) -ne $target.adapted_sha256) { throw 'Material asset hash mismatch.' }
        }
    }
    if (-not $aliases.Count) { throw 'No reviewed material aliases in this stage.' }
    $variant = Checked-Path $gameRoot 'update\common\shaders\win32_30'
    $expectedContainers = @($assets.modern_corpus.PSObject.Properties)
    $actualContainers = @(Get-ChildItem -LiteralPath $variant -Filter *.fxc -File)
    if (-not $expectedContainers.Count -or $actualContainers.Count -ne $expectedContainers.Count) { throw 'The full modern shader variant is required.' }
    foreach ($container in $expectedContainers) {
        if ($container.Name -notmatch '^[a-zA-Z0-9_]+\.fxc$' -or
            (Hash (Checked-Path $variant $container.Name)) -ne $container.Value) { throw "Modern shader package mismatch: $($container.Name)" }
    }
    if ((Hash (Checked-Path $gameRoot 'd3d9.dll')) -ne '280e2bc15485bb7b944d47bad9e7d553b6e63eba3afb97bdbc546d45fcc203c4') { throw 'This test requires the audited ENB 0.163 wrapper.' }
    $text = Get-Content -LiteralPath (Checked-Path $gameRoot 'plugins\GTAIV.EFLC.FusionFix.ini') -Raw
    $sections = [regex]::Matches($text, '(?ims)^\[ENBCompatibility\][^\r\n]*\r?\n(?<body>.*?)(?=^\[|\z)')
    if ($sections.Count -ne 1) { throw 'Expected exactly one ENBCompatibility section.' }
    $required = @{ Mode = '1'; PostFxBridge = '1'; FusionShaderPackage = '1'; ShaderConstantInjection = '1'; ShadowPipelineFixes = '1'; ReplacePostFX = '0' }
    foreach ($key in $required.Keys) {
        $settingMatches = [regex]::Matches($sections[0].Groups['body'].Value, ('(?im)^' + $key + '\s*=\s*(?<value>[^\r\n]*)'))
        if ($settingMatches.Count -ne 1 -or $settingMatches[0].Groups['value'].Value -notmatch ('^' + $required[$key] + '\s*(?://.*)?$')) { throw "Active modern bridge required: $key = $($required[$key])" }
    }
    foreach ($name in $aliases.Keys) {
        $target = Checked-Path $gameRoot ('shaderinput\' + $name)
        if ((Test-Path -LiteralPath $target) -and -not (Test-Path -LiteralPath $target -PathType Leaf)) { throw 'An alias target is not a file.' }
    }
    if (-not (Test-Path -LiteralPath $snapshotManifest)) {
        if (Test-Path -LiteralPath $snapshot) { throw 'An incomplete material snapshot exists; preserve and inspect it.' }
        New-Item -ItemType Directory -Path $snapshot | Out-Null
        $entries = @()
        foreach ($name in ($aliases.Keys | Sort-Object)) {
            $target = Checked-Path $gameRoot ('shaderinput\' + $name)
            $exists = Test-Path -LiteralPath $target -PathType Leaf
            $digest = $null
            if ($exists) {
                $digest = Hash $target
                $saved = Checked-Path $snapshot $name
                Copy-Item -LiteralPath $target -Destination $saved
                if ((Hash $saved) -ne $digest) { throw 'Material backup verification failed.' }
            }
            $entries += [pscustomobject]@{ name = $name; existed = $exists; sha256 = $digest }
        }
        [pscustomobject]@{ format = 1; game = $gameRoot; entries = $entries } |
            ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $snapshotManifest -Encoding UTF8
    }
}
if (-not (Test-Path -LiteralPath $snapshotManifest)) { throw 'No material snapshot exists.' }
$manifest = Get-Content -LiteralPath $snapshotManifest -Raw | ConvertFrom-Json
$names = @($manifest.entries | ForEach-Object { $_.name })
if ($manifest.format -ne 1 -or $manifest.game -ne $gameRoot -or -not $names.Count -or
    @($names | Sort-Object -Unique).Count -ne $names.Count) { throw 'Material snapshot does not match this game.' }
if ($Action -eq 'Apply' -and @($names | Where-Object { -not $aliases.ContainsKey($_) }).Count) {
    throw 'Stage drops previously snapshotted aliases. Restore before changing to a smaller stage.'
}
foreach ($entry in $manifest.entries) {
    if ($entry.name -cnotmatch '^[pv]sh[0-9A-F]{8}\.txt$') { throw 'Invalid snapshot alias.' }
    if ($entry.existed -and (Hash (Checked-Path $snapshot $entry.name)) -ne $entry.sha256) { throw 'Material backup hash mismatch.' }
    $target = Checked-Path $gameRoot ('shaderinput\' + $entry.name)
    if ((Test-Path -LiteralPath $target) -and -not (Test-Path -LiteralPath $target -PathType Leaf)) { throw 'An alias target is not a file.' }
}
if ($Action -eq 'Apply') {
    $newNames = @($aliases.Keys | Where-Object { $_ -notin $names } | Sort-Object)
    if ($newNames.Count) {
        $additional = @()
        foreach ($name in $newNames) {
            $target = Checked-Path $gameRoot ('shaderinput\' + $name)
            $saved = Checked-Path $snapshot $name
            if (Test-Path -LiteralPath $saved) { throw 'An unrecorded backup exists from an interrupted upgrade; preserve and inspect it.' }
            $exists = Test-Path -LiteralPath $target -PathType Leaf
            $digest = $null
            if ($exists) {
                $digest = Hash $target
                Copy-Item -LiteralPath $target -Destination $saved
                if ((Hash $saved) -ne $digest) { throw 'Additional alias backup verification failed.' }
            }
            $additional += [pscustomobject]@{ name = $name; existed = $exists; sha256 = $digest }
        }
        $expanded = [pscustomobject]@{ format = 1; game = $gameRoot; entries = @($manifest.entries) + $additional }
        $temporaryManifest = Checked-Path $snapshot ('manifest-' + [guid]::NewGuid().ToString('N') + '.tmp')
        $previousManifest = Checked-Path $snapshot ('manifest-before-upgrade-' + [guid]::NewGuid().ToString('N') + '.json')
        try {
            [IO.File]::WriteAllText($temporaryManifest, ($expanded | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
            # Commit the complete backup inventory before installing any alias.
            [IO.File]::Replace($temporaryManifest, $snapshotManifest, $previousManifest)
        } finally {
            if (Test-Path -LiteralPath $temporaryManifest -PathType Leaf) { Remove-Item -LiteralPath $temporaryManifest }
        }
        $manifest = $expanded
        Write-Host "Extended the original snapshot for $($additional.Count) additional aliases."
    }
}
function Restore-Aliases {
    foreach ($entry in $manifest.entries) {
        $target = Checked-Path $gameRoot ('shaderinput\' + $entry.name)
        if ($entry.existed) {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath (Checked-Path $snapshot $entry.name) -Destination $target -Force
            if ((Hash $target) -ne $entry.sha256) { throw 'Material restore verification failed.' }
        } elseif (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target }
    }
}
if ($Action -eq 'Restore') {
    Restore-Aliases
    Write-Host 'Pre-test material aliases restored. Other ENB effects and bridge files retained.'
    exit
}
try {
    New-Item -ItemType Directory -Force -Path (Checked-Path $gameRoot 'shaderinput') | Out-Null
    foreach ($name in ($aliases.Keys | Sort-Object)) {
        $target = Checked-Path $gameRoot ('shaderinput\' + $name)
        Copy-Item -LiteralPath (Checked-Path $stageRoot ('shaderinput\' + $name)) -Destination $target -Force
        if ((Hash $target) -ne $aliases[$name]) { throw 'Installed material hash mismatch.' }
    }
} catch {
    $applyFailure = $_
    Restore-Aliases
    throw $applyFailure
}
Write-Host "Installed $($aliases.Count) experimental modern aliases. Compare the same scene with ENB enabled; retain the preset and bridge settings."
Write-Host "Restore: & '$PSCommandPath' -Kit '$kitRoot' -Game '$gameRoot' -Action Restore"
