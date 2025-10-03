@echo off
setlocal enabledelayedexpansion

REM Read input file - parse variable assignments
for /f "usebackq tokens=1,2 delims==" %%a in ("%~1") do (
    set "line=%%a"
    if "!line:~0,1!" neq "#" if "!line:~0,1!" neq "@" (
        set "%%a=%%b"
    )
)

REM Simulate calculation time
timeout /t 1 /nobreak >nul

REM Calculate pressure = n_mol * 8.314 * T_kelvin / V_m3
REM Using R = 8314/1000 = 8.314 J/(mol·K)
call :calc_ 4 (%n_mol%)*8314*(%T_kelvin%)/1000/(%V_m3%)
echo pressure = !calc_v!> output.txt

echo Done
goto :EOF

:calc_
REM Decimal calculation subroutine
REM Usage: call :calc_ <decimal_places> <expression>
REM Result stored in calc_v
set scale_=1
set calc_v=
for /l %%i in (1,1,%1) do set /a scale_*=10
set /a "calc_v=!scale_!*%~2"
set /a calc_v1=!calc_v!/!scale_!
set /a calc_v2=!calc_v!-!calc_v1!*!scale_!
if !calc_v2! lss 0 set /a calc_v2=-!calc_v2!
REM Pad decimal part with leading zeros if needed
set "calc_v2=0000!calc_v2!"
set "calc_v2=!calc_v2:~-%1!"
set calc_v=!calc_v1!.!calc_v2!
goto :EOF
