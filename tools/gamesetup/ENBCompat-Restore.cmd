@echo off
rem Puts the install back exactly as it was before the ENB compatibility test.
rem Restores FusionFix's d3d9.dll, .asi and .ini from _ENBCompat_Backup, and
rem removes everything the test added.

setlocal
set "G=%~dp0"
set "B=%G%_ENBCompat_Backup"

if not exist "%B%\d3d9.dll" (
    echo Backup folder not found: %B%
    echo Nothing restored.
    pause
    exit /b 1
)

echo Undoing any .off renames left by ENBCompat-Mode...
if exist "%G%plugins\GTAIV.EFLC.FusionFix.asi.off" move /y "%G%plugins\GTAIV.EFLC.FusionFix.asi.off" "%G%plugins\GTAIV.EFLC.FusionFix.asi" >nul
if exist "%G%update\common\shaders\win32_30.off"   move /y "%G%update\common\shaders\win32_30.off"   "%G%update\common\shaders\win32_30"   >nul
if exist "%G%d3d9.dll.off"                         del /q "%G%d3d9.dll.off"
if exist "%G%update\common\shaders\win32_30_nv8.off" rd /s /q "%G%update\common\shaders\win32_30_nv8.off"

echo Restoring FusionFix files...
copy /y "%B%\d3d9.dll"                              "%G%d3d9.dll"                              >nul
copy /y "%B%\d3d9.cfg"                              "%G%d3d9.cfg"                              >nul
copy /y "%B%\plugins\GTAIV.EFLC.FusionFix.asi"      "%G%plugins\GTAIV.EFLC.FusionFix.asi"      >nul
copy /y "%B%\plugins\GTAIV.EFLC.FusionFix.ini"      "%G%plugins\GTAIV.EFLC.FusionFix.ini"      >nul
if exist "%B%\plugins\GTAIV.EFLC.FusionFix.cfg" copy /y "%B%\plugins\GTAIV.EFLC.FusionFix.cfg" "%G%plugins\GTAIV.EFLC.FusionFix.cfg" >nul

echo Removing ENB and iCEnhancer files...
for %%f in (enbseries.ini enbeffect.fx enbbloom.fx enbclouds.fx enbdetail.dds enbmoon.tga enbmoonbump.tga key_codes.txt enbseries.log enblocal.ini enbclouds.png enbspritelight.png enbspriteray.png enbstars.png icenhancer.asi enbeffect.fx.orig enbeffect.fx.probe) do (
    if exist "%G%%%f" del /q "%G%%%f"
)
if exist "%G%shaderinput"       rd /s /q "%G%shaderinput"
if exist "%G%shaderinput.orig"  rd /s /q "%G%shaderinput.orig"
if exist "%G%shaderinput.probe" rd /s /q "%G%shaderinput.probe"

echo Restoring game content iCEnhancer replaced...
set "GC=%B%\gamecontent"
if exist "%GC%\common\text\american.gxt"              copy /y "%GC%\common\text\american.gxt"              "%G%common\text\american.gxt"              >nul
if exist "%GC%\pc\data\effects\gtaRainRender.xml"     copy /y "%GC%\pc\data\effects\gtaRainRender.xml"     "%G%pc\data\effects\gtaRainRender.xml"     >nul
if exist "%GC%\pc\data\effects\gtaStormRender.xml"    copy /y "%GC%\pc\data\effects\gtaStormRender.xml"    "%G%pc\data\effects\gtaStormRender.xml"    >nul
if exist "%GC%\pc\textures\skydome.wtd"               copy /y "%GC%\pc\textures\skydome.wtd"               "%G%pc\textures\skydome.wtd"               >nul
if exist "%GC%\update\common\data\visualsettings.dat" copy /y "%GC%\update\common\data\visualsettings.dat" "%G%update\common\data\visualsettings.dat" >nul

echo Removing the staged stock-shader overlay...
if exist "%G%update\common\shaders\win32_30_nv8"     rd /s /q "%G%update\common\shaders\win32_30_nv8"
if exist "%G%update\common\shaders\win32_30_nv7"     rd /s /q "%G%update\common\shaders\win32_30_nv7"
if exist "%G%update\common\shaders\win32_30_nv6"     rd /s /q "%G%update\common\shaders\win32_30_nv6"
if exist "%G%update\common\shaders\win32_30_low_ati" rd /s /q "%G%update\common\shaders\win32_30_low_ati"
if exist "%G%update\common\shaders\win32_30_atidx10" rd /s /q "%G%update\common\shaders\win32_30_atidx10"

echo Removing diagnostics...
if exist "%G%ENBCompat.log" del /q "%G%ENBCompat.log"
if exist "%G%ENBCompat"     rd /s /q "%G%ENBCompat"

echo.
echo Done. FusionFix 5.0.1 is back as it was.
echo The backup folder is left in place: %B%
pause
