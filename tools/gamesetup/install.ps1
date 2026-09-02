<#
.SYNOPSIS
Sets a GTA IV install up for ENB compatibility testing, reversibly.

.DESCRIPTION
Everything this does can be undone by ENBCompat-Restore.cmd, which it also
installs. It backs up every file it is about to replace into
<game>\_ENBCompat_Backup first and refuses to run if that would overwrite an
existing backup, so a second run cannot destroy the record of the original
install.

What it does:

  * backs up d3d9.dll, d3d9.cfg, the FusionFix .asi/.ini/.cfg, and any game
    content an ENB preset is going to replace
  * installs an ENBSeries preset from an extracted preset folder
  * installs the FusionFix build from this repository's bin\ folder
  * appends an [ENBCompatibility] section to the FusionFix ini
  * stages the stock-shader overlay so FusionShaderPackage = 0 has somewhere to
    fall through to
  * copies the ENBCompat-*.cmd helper scripts into the game folder

.PARAMETER Game
The GTAIV folder holding GTAIV.exe, common\ and update\.

.PARAMETER Preset
An extracted ENB preset folder -- the "Wrapper version" folder of an ENBSeries
download, or a preset laid out the same way.

.PARAMETER Selective
Keep FusionFix's shaders except in the containers an ENB preset needs from
stock, instead of running entirely on stock shaders.

.EXAMPLE
.\install.ps1 -Game "C:\Games\Steam\steamapps\common\Grand Theft Auto IV\GTAIV" `
              -Preset "C:\temp\enbseries_gta4_v0163\Wrapper version"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Game,
    [Parameter(Mandatory)][string]$Preset,
    [switch]$Selective,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backup = Join-Path $Game '_ENBCompat_Backup'

function Require-Path([string]$path, [string]$what) {
    if (-not (Test-Path -LiteralPath $path)) { throw "$what not found: $path" }
}

Require-Path (Join-Path $Game 'GTAIV.exe') 'GTAIV.exe'
Require-Path $Preset 'Preset folder'
Require-Path (Join-Path $repo 'bin\GTAIV.EFLC.FusionFix.asi') 'Built .asi (run premake5 + msbuild first)'

if ((Test-Path -LiteralPath $backup) -and -not $Force) {
    throw "A backup already exists at $backup. Run ENBCompat-Restore.cmd first, or pass -Force to keep it as-is."
}

if (Get-Process GTAIV -ErrorAction SilentlyContinue) {
    throw 'GTAIV.exe is running. Close it first.'
}

# --- back up whatever is about to change -----------------------------------

Write-Host 'Backing up...'
foreach ($dir in 'plugins', 'gamecontent\common\text', 'gamecontent\pc\data\effects',
                 'gamecontent\pc\textures', 'gamecontent\update\common\data') {
    New-Item -ItemType Directory -Force -Path (Join-Path $backup $dir) | Out-Null
}
foreach ($f in 'd3d9.dll', 'd3d9.cfg') {
    $src = Join-Path $Game $f
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src (Join-Path $backup $f) -Force }
}
foreach ($f in 'GTAIV.EFLC.FusionFix.asi', 'GTAIV.EFLC.FusionFix.ini', 'GTAIV.EFLC.FusionFix.cfg') {
    $src = Join-Path $Game "plugins\$f"
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src (Join-Path $backup "plugins\$f") -Force }
}
# Content an ENB preset commonly ships its own copy of.
$content = @{
    'common\text\american.gxt'                = 'gamecontent\common\text'
    'pc\data\effects\gtaRainRender.xml'       = 'gamecontent\pc\data\effects'
    'pc\data\effects\gtaStormRender.xml'      = 'gamecontent\pc\data\effects'
    'pc\textures\skydome.wtd'                 = 'gamecontent\pc\textures'
    'update\common\data\visualsettings.dat'   = 'gamecontent\update\common\data'
}
foreach ($rel in $content.Keys) {
    $src = Join-Path $Game $rel
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src (Join-Path $backup $content[$rel]) -Force }
}

# --- install ----------------------------------------------------------------

Write-Host 'Installing the ENB preset...'
Get-ChildItem -LiteralPath $Preset -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName (Join-Path $Game $_.Name) -Force
}
$presetShaders = Join-Path $Preset 'shaderinput'
if (Test-Path -LiteralPath $presetShaders) {
    $dst = Join-Path $Game 'shaderinput'
    if (Test-Path -LiteralPath $dst) { Remove-Item -LiteralPath $dst -Recurse -Force }
    Copy-Item -LiteralPath $presetShaders $dst -Recurse -Force
}

# ENBSeries ships with a proxy chain enabled that points at a DLL which is not
# there. Left alone it is a confusing way to fail.
$enbIni = Join-Path $Game 'enbseries.ini'
if (Test-Path -LiteralPath $enbIni) {
    $text = (Get-Content -LiteralPath $enbIni -Raw) -replace 'EnableProxyLibrary=true', 'EnableProxyLibrary=false'
    # F12 is Steam's screenshot key, so the effect toggle never reaches ENB.
    $text = $text -replace 'KeyUseEffect=123', 'KeyUseEffect=122'
    Set-Content -LiteralPath $enbIni -Value $text -Encoding ASCII -NoNewline
}

Write-Host 'Installing the FusionFix build...'
Copy-Item -LiteralPath (Join-Path $repo 'bin\GTAIV.EFLC.FusionFix.asi') `
          (Join-Path $Game 'plugins\GTAIV.EFLC.FusionFix.asi') -Force

$ini = Join-Path $Game 'plugins\GTAIV.EFLC.FusionFix.ini'
$iniText = Get-Content -LiteralPath $ini -Raw
if ($iniText -notmatch '\[ENBCompatibility\]') {
    Write-Host 'Appending [ENBCompatibility]...'
    $section = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'ENBCompatibility.ini') -Raw
    Set-Content -LiteralPath $ini -Value ($iniText.TrimEnd() + "`r`n`r`n" + $section) -Encoding ASCII -NoNewline
}

Write-Host 'Staging the stock-shader overlay...'
$mk = Join-Path $repo 'tools\shader_dump\make_vanilla_package.py'
$mode = if ($Selective) { '--selective' } else { '--stage-extras' }
& python $mk --game $Game $mode
if ($LASTEXITCODE -ne 0) { throw "make_vanilla_package.py failed ($LASTEXITCODE)" }

Write-Host 'Installing helper scripts...'
Get-ChildItem -LiteralPath $PSScriptRoot -Filter 'ENBCompat-*.cmd' | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName (Join-Path $Game $_.Name) -Force
}

Write-Host ''
Write-Host 'Done. Before launching:'
Write-Host '  * d3d9.cfg must be [MAIN] API = 0 -- ENB does nothing on the Vulkan path'
Write-Host '  * set Depth of Field to Low or higher in the graphics menu'
Write-Host ''
Write-Host 'Undo everything with ENBCompat-Restore.cmd in the game folder.'
