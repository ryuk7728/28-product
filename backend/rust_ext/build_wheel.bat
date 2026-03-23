@echo off
setlocal

if not "%VIRTUAL_ENV%"=="" (
  set "PYTHON_EXE=%VIRTUAL_ENV%\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

echo Building wheel with:
echo   PYTHON_EXE=%PYTHON_EXE%

"%PYTHON_EXE%" -m maturin build --release -i "%PYTHON_EXE%"
if errorlevel 1 exit /b 1

echo Installing wheel...
"%PYTHON_EXE%" -m pip install --force-reinstall target\wheels\rl428_minimax_rust-*.whl

endlocal
