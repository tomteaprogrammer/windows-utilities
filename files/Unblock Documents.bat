@echo off
REM ---------------------------------------------------------------------
REM  Unblock Documents - launcher
REM
REM  Double-click this file to open the window, or drag a folder onto it
REM  to start with that folder already filled in.
REM ---------------------------------------------------------------------
setlocal EnableExtensions EnableDelayedExpansion
title Unblock Documents
cd /d "%~dp0"

set "SCRIPT=%~dp0unblock_documents.py"
if not exist "%SCRIPT%" (
    echo Could not find unblock_documents.py next to this batch file.
    echo Keep both files in the same folder.
    echo.
    pause
    exit /b 1
)

REM --- find Python ------------------------------------------------------
set "PY="
where py >nul 2>&1
if %errorlevel%==0 set "PY=py -3"
if not defined PY (
    where python >nul 2>&1
    if !errorlevel!==0 set "PY=python"
)
if not defined PY (
    echo Python was not found on this computer.
    echo Install it from https://www.python.org/downloads/ and tick
    echo "Add python.exe to PATH" during setup, then run this file again.
    echo.
    pause
    exit /b 1
)

REM --- folder to start with --------------------------------------------
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%CD%"

:menu
cls
echo ======================================================================
echo   Unblock Documents
echo ======================================================================
echo   Folder: %TARGET%
echo.
echo   [1]  Open the window  (browse, preview, unblock)
echo   [2]  Console: scan + dry run only  (changes nothing)
echo   [3]  Console: scan, dry run, then ask before unblocking
echo   [4]  Type a different folder
echo   [5]  Quit
echo.
set "CHOICE="
set /p "CHOICE=Choose 1-5: "

if "%CHOICE%"=="1" goto gui
if "%CHOICE%"=="2" goto dryrun
if "%CHOICE%"=="3" goto unblock
if "%CHOICE%"=="4" goto retarget
if "%CHOICE%"=="5" exit /b 0
goto menu

:retarget
echo.
set "NEWTARGET="
set /p "NEWTARGET=Full path of the folder to scan: "
if not "%NEWTARGET%"=="" set "TARGET=%NEWTARGET%"
goto menu

:gui
%PY% "%SCRIPT%" --path "%TARGET%"
if errorlevel 1 (
    echo.
    echo The window closed with an error - see the message above.
    pause
)
goto menu

:dryrun
echo.
%PY% "%SCRIPT%" --cli --path "%TARGET%" --dry-run
echo.
pause
goto menu

:unblock
echo.
%PY% "%SCRIPT%" --cli --path "%TARGET%"
echo.
pause
goto menu
