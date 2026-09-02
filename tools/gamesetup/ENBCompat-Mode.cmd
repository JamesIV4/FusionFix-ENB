@echo off
rem Switches between the test configurations without editing anything by hand.
rem
rem   ENBCompat-Mode C    ENB only, FusionFix disabled      (isolates ENB)
rem   ENBCompat-Mode D    ENB + FusionFix in ENB mode       (the thing being built)
rem   ENBCompat-Mode B    FusionFix normal, ENB disabled    (sanity check)
rem
rem It works by renaming files and folders to and from a .off suffix, nothing
rem more, so switching back and forth is safe and instant:
rem
rem   plugins\GTAIV.EFLC.FusionFix.asi    FusionFix on / off
rem   d3d9.dll                            ENB on / off
rem   update\common\shaders\win32_30      the FusionFix shader package
rem   update\common\shaders\win32_30_nv8  the staged stock-shader overlay
rem
rem The shader package matters even with the .asi off: the game reads update\
rem natively, so leaving it in place could feed FusionFix's shaders to a
rem configuration that is supposed to be running stock ones.

setlocal
set "G=%~dp0"
set "ASI=%G%plugins\GTAIV.EFLC.FusionFix.asi"
set "ENB=%G%d3d9.dll"
set "PKG=%G%update\common\shaders\win32_30"
set "NV8=%G%update\common\shaders\win32_30_nv8"

if /i "%~1"=="C" goto :modeC
if /i "%~1"=="D" goto :modeD
if /i "%~1"=="B" goto :modeB

echo Usage: ENBCompat-Mode [C^|D^|B]
echo.
echo   C   ENB only, FusionFix disabled   - does the ENB work on Complete Edition at all
echo   D   ENB + FusionFix in ENB mode    - the configuration being built
echo   B   FusionFix only, ENB disabled   - sanity check that nothing else broke
echo.
goto :report

:modeC
rem ENB against the stock game. Both FusionFix halves stand down: the .asi, and
rem the shader package the game would otherwise mount by itself.
if exist "%ASI%"     move /y "%ASI%"     "%ASI%.off" >nul
if exist "%ENB%.off" move /y "%ENB%.off" "%ENB%"     >nul
if exist "%PKG%"     move /y "%PKG%"     "%PKG%.off" >nul
if exist "%NV8%"     move /y "%NV8%"     "%NV8%.off" >nul
echo Configuration C: ENB only, FusionFix disabled, stock shaders.
goto :report

:modeD
rem The .asi redirects shader lookups to win32_30_nv8, so the package stays in
rem place but inert -- nothing looks in it.
if exist "%ASI%.off" move /y "%ASI%.off" "%ASI%" >nul
if exist "%ENB%.off" move /y "%ENB%.off" "%ENB%" >nul
if exist "%PKG%.off" move /y "%PKG%.off" "%PKG%" >nul
if exist "%NV8%.off" move /y "%NV8%.off" "%NV8%" >nul
echo Configuration D: ENB + FusionFix in ENB mode.
goto :report

:modeB
if exist "%ASI%.off" move /y "%ASI%.off" "%ASI%"     >nul
if exist "%ENB%"     move /y "%ENB%"     "%ENB%.off" >nul
if exist "%PKG%.off" move /y "%PKG%.off" "%PKG%"     >nul
if exist "%NV8%.off" move /y "%NV8%.off" "%NV8%"     >nul
echo Configuration B: FusionFix only, ENB disabled.
echo   Set Mode = 0 in plugins\GTAIV.EFLC.FusionFix.ini for stock FusionFix.
goto :report

:report
echo.
echo Current state:
set "S1=off"
set "S2=off"
set "S3=off"
set "S4=off"
if exist "%ASI%" set "S1=ON"
if exist "%ENB%" set "S2=ON"
if exist "%PKG%" set "S3=ON"
if exist "%NV8%" set "S4=ON"
echo   FusionFix .asi     %S1%
echo   ENB d3d9.dll       %S2%
echo   FusionFix shaders  %S3%
echo   stock overlay nv8  %S4%
echo.
pause
