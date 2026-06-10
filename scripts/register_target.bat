@echo off
setlocal EnableDelayedExpansion
REM register_target.bat - add/remove/list an IP or domain + port in the Tier2
REM scope allowlist (SSM StringList /tier2/scope-allowlist). Fail-closed.
REM Windows cmd.exe equivalent of register_target.sh. Requires awscli v2.

set "REGION=%AWS_REGION%"
if "%REGION%"=="" set "REGION=%AWS_DEFAULT_REGION%"
if "%REGION%"=="" set "REGION=us-east-1"
set "PARAM=%SCOPE_PARAM_NAME%"
if "%PARAM%"=="" set "PARAM=/tier2/scope-allowlist"

where aws >nul 2>&1
if errorlevel 1 ( echo ERROR: awscli not found on PATH.& exit /b 1 )

if "%~1"=="" goto :usage
if /i "%~1"=="-h"     goto :usage
if /i "%~1"=="--help" goto :usage
if /i "%~1"=="--list" goto :list

set "HOST=%~1"
set "PORT=%~2"
set "ACTION=add"
if /i "%~3"=="--remove" set "ACTION=remove"
if "%HOST%"=="" goto :usage
if "%PORT%"=="" goto :usage

call :validate_host "%HOST%"
if errorlevel 1 ( echo ERROR: '%HOST%' is not a valid IPv4 address or domain name.& exit /b 1 )
call :validate_port "%PORT%"
if errorlevel 1 ( echo ERROR: Port '%PORT%' must be an integer 1-65535.& exit /b 1 )
set "ENTRY=%HOST%:%PORT%"

REM --- read current allowlist (comma-joined; empty if unset) ---
set "CURRENT="
for /f "usebackq delims=" %%i in (`aws ssm get-parameter --name "%PARAM%" --region "%REGION%" --query "Parameter.Value" --output text 2^>nul`) do set "CURRENT=%%i"

set "FOUND="
echo ,!CURRENT!,| findstr /c:",!ENTRY!," >nul && set "FOUND=1"

if /i "%ACTION%"=="remove" goto :remove

REM --- add ---
if defined FOUND ( echo '!ENTRY!' is already registered; nothing to do.& exit /b 0 )
if defined CURRENT ( set "NEW=!CURRENT!,!ENTRY!" ) else ( set "NEW=!ENTRY!" )
echo Registering !ENTRY! ...
call :write "!NEW!"
if errorlevel 1 exit /b 1
goto :show

:remove
if not defined FOUND ( echo ERROR: '!ENTRY!' is not in the allowlist; nothing to remove.& exit /b 1 )
set "NEW="
for %%E in ("!CURRENT:,=" "!") do (
  set "ITEM=%%~E"
  if /i not "!ITEM!"=="!ENTRY!" (
    if defined NEW ( set "NEW=!NEW!,!ITEM!" ) else ( set "NEW=!ITEM!" )
  )
)
if not defined NEW ( echo ERROR: Refusing to write an empty allowlist ^(fail-closed^). Use set_scope.ps1 to reset.& exit /b 1 )
echo Removing !ENTRY! ...
call :write "!NEW!"
if errorlevel 1 exit /b 1
goto :show

:show
echo Allowlist for %PARAM% is now:
call :printlist
exit /b 0

:list
echo Scope allowlist ^(%PARAM%, region %REGION%^):
call :printlist
exit /b 0

REM ===== subroutines =====

:write
aws ssm put-parameter --name "%PARAM%" --region "%REGION%" --type StringList --overwrite --value "%~1" >nul
if errorlevel 1 ( echo ERROR: failed to write SSM parameter %PARAM%.& exit /b 1 )
exit /b 0

:printlist
set "VAL="
for /f "usebackq delims=" %%i in (`aws ssm get-parameter --name "%PARAM%" --region "%REGION%" --query "Parameter.Value" --output text 2^>nul`) do set "VAL=%%i"
if not defined VAL ( echo   ^(empty - fail-closed^)& exit /b 0 )
for %%E in ("!VAL:,=" "!") do echo   - %%~E
exit /b 0

:validate_port
echo %~1| findstr /r "^[0-9][0-9]*$" >nul || exit /b 1
if %~1 LSS 1 exit /b 1
if %~1 GTR 65535 exit /b 1
exit /b 0

:validate_host
set "H=%~1"
echo !H!| findstr /r "^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$" >nul
if not errorlevel 1 (
  call :validate_ipv4 "!H!"
  exit /b !errorlevel!
)
echo !H!| findstr /r "^[a-zA-Z0-9][a-zA-Z0-9.\-]*\.[a-zA-Z][a-zA-Z]*$" >nul || exit /b 1
exit /b 0

:validate_ipv4
for /f "tokens=1-4 delims=." %%a in ("%~1") do (
  set "O1=%%a" & set "O2=%%b" & set "O3=%%c" & set "O4=%%d"
)
for %%o in (!O1! !O2! !O3! !O4!) do (
  if %%o GTR 255 exit /b 1
)
exit /b 0

:usage
echo register_target.bat - add an IP or domain + port to the Tier2 scope allowlist
echo   (SSM StringList %PARAM%). Fail-closed; ADDS (append + dedupe).
echo.
echo Usage:
echo   register_target.bat ^<ip-or-domain^> ^<port^>            add host:port
echo   register_target.bat ^<ip-or-domain^> ^<port^> --remove   remove host:port
echo   register_target.bat --list                           show current allowlist
echo   register_target.bat --help
echo.
echo Examples:
echo   register_target.bat 54.84.126.64 80
echo   register_target.bat sandbox-defender.example.com 443
echo   register_target.bat 10.0.0.5 8080 --remove
echo.
echo Env: AWS_REGION/AWS_DEFAULT_REGION (default us-east-1),
echo      SCOPE_PARAM_NAME (default /tier2/scope-allowlist). Requires awscli v2.
exit /b 0
