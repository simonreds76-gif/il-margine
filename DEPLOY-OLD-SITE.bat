@echo off
cd /d "%~dp0"
title Deploy old site - il-margine
echo.
echo === Restoring old site to production ===
echo.
echo Folder: %CD%
echo.
git --version
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Git not found. Install Git or run from Cursor Terminal.
    goto end
)
echo.
echo Pushing to GitHub (you may be asked to log in)...
echo.
git push origin main --force
echo.
if %ERRORLEVEL% EQU 0 (
    echo === SUCCESS ===
    echo Vercel will deploy in 1-2 minutes. Your live site will be the old version.
) else (
    echo === PUSH FAILED ===
    echo Try in Cursor: Terminal - New Terminal, then run:
    echo   git push origin main --force
)
:end
echo.
pause
