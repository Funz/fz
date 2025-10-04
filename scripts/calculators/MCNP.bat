@echo on

set PATH="c:\MCNP\MCNP6\bin\windows";%PATH%
set DATAPATH="c:\MCNP\MCNP_DATA"

cd /d %~dp1
start mcnp6.exe inp=%*

for /f "TOKENS=1" %%a in ('wmic PROCESS where "Name='mcnp6.exe'" get ProcessID ^| findstr [0-9]') do set PID=%%a
(echo %PID%) > PID.txt
