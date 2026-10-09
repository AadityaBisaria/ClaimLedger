@echo off
setlocal
set "PROJECT=%~dp0"
if exist "%PROJECT%.venv\Scripts\python.exe" (
  "%PROJECT%.venv\Scripts\python.exe" "%PROJECT%server.py"
) else if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "%PROJECT%server.py"
) else (
  python "%PROJECT%server.py"
)
pause
