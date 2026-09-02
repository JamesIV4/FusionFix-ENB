@echo off
rem Bisects an ENB preset one component at a time, on top of ENBSeries 0.163.
rem
rem   ENBCompat-Mix base      0.163 only                         (known good)
rem   ENBCompat-Mix shaders   0.163 + iCEnhancer's shaderinput
rem   ENBCompat-Mix effect    0.163 + iCEnhancer's enbeffect.fx
rem   ENBCompat-Mix fx        0.163 + iCEnhancer's bloom/clouds/textures
rem   ENBCompat-Mix all       iCEnhancer's whole preset, no .asi
rem
rem Why: iCEnhancer 4's .asi cannot run here -- it does 1.0.4.0-specific work on
rem the executable and faults immediately on Complete Edition -- but its preset
rem is where the look actually lives. The question worth answering is how much of
rem that preset ENBSeries 0.163 can run on its own, and the only way to find out
rem is one component at a time from a configuration that is known to work.
rem
rem None of these load icenhancer.asi. Leave LoadPluginAfterSpoof empty in
rem plugins\GTAIV.EFLC.FusionFix.ini.

setlocal
set "G=%~dp0"
set "B=%G%_ENBCompat_Backup"
set "E=%B%\enb0163"
set "I=%B%\ice40"

if not exist "%E%" echo Snapshot missing: %E% & goto :report
if not exist "%I%" echo Snapshot missing: %I% & goto :report

if /i "%~1"=="base"    goto :base
if /i "%~1"=="shaders" goto :shaders
if /i "%~1"=="effect"  goto :effect
if /i "%~1"=="fx"      goto :fx
if /i "%~1"=="all"     goto :all

echo Usage: ENBCompat-Mix [base^|shaders^|effect^|fx^|all]
echo.
echo   base      ENBSeries 0.163 only, the known-good configuration
echo   shaders   base plus iCEnhancer's 12 shaderinput replacements
echo   effect    base plus iCEnhancer's enbeffect.fx
echo   fx        base plus iCEnhancer's enbbloom / enbclouds and textures
echo   all       iCEnhancer's whole preset, minus its .asi
echo.
goto :report

:reset
rem Always rebuild from the 0.163 baseline so a run never inherits leftovers
rem from the previous one.
if exist "%G%shaderinput" rd /s /q "%G%shaderinput"
for %%f in (enbclouds.png enbspritelight.png enbspriteray.png enbstars.png) do (
    if exist "%G%%%f" del /q "%G%%%f"
)
xcopy /e /i /y /q "%E%" "%G%" >nul
if exist "%G%icenhancer.asi"       del /q "%G%icenhancer.asi"
exit /b 0

:base
call :reset
echo Mix: ENBSeries 0.163 only.
goto :report

:shaders
call :reset
rd /s /q "%G%shaderinput"
xcopy /e /i /y /q "%I%\shaderinput" "%G%shaderinput" >nul
echo Mix: 0.163 + iCEnhancer shaderinput.
goto :report

:effect
call :reset
copy /y "%I%\enbeffect.fx" "%G%enbeffect.fx" >nul
echo Mix: 0.163 + iCEnhancer enbeffect.fx.
goto :report

:fx
call :reset
for %%f in (enbbloom.fx enbclouds.fx enbdetail.dds enbclouds.png enbspritelight.png enbspriteray.png enbstars.png) do (
    if exist "%I%\%%f" copy /y "%I%\%%f" "%G%%%f" >nul
)
echo Mix: 0.163 + iCEnhancer bloom/clouds/textures.
goto :report

:all
call :reset
rd /s /q "%G%shaderinput"
xcopy /e /i /y /q "%I%" "%G%" >nul
if exist "%G%icenhancer.asi" del /q "%G%icenhancer.asi"
echo Mix: iCEnhancer's whole preset, no .asi.
goto :report

:report
echo.
set "S1=none"
if exist "%G%shaderinput" for /f %%n in ('dir /b "%G%shaderinput\*.txt" 2^>nul ^| find /c /v ""') do set "S1=%%n"
for %%f in ("%G%enbeffect.fx") do set "S2=%%~zf"
echo   shaderinput files   %S1%      ^(4 = 0.163, 12 = iCEnhancer^)
echo   enbeffect.fx bytes  %S2%   ^(23825 = 0.163, 15024 = iCEnhancer^)
echo.
pause
