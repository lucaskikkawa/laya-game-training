@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
set "LAYA_HOME=%CD%"
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente .venv não encontrado. Execute scripts\instalar.ps1 primeiro.
    pause
    exit /b 1
)
set "LAYA_PARTIDAS="
set /p "LAYA_PARTIDAS=Quantas partidas deseja jogar? "
rem A entrada segue pelo ambiente, sem interpolar texto do usuário no comando.
".venv\Scripts\python.exe" -c "import os,sys; from jogos.snake.__main__ import main; sys.argv = ['jogos.snake', '--partidas', os.environ.get('LAYA_PARTIDAS', ''), '--modo', 'rapido', '--sem-janela']; sys.exit(main())"
set "LAYA_RESULTADO=%ERRORLEVEL%"
echo.
pause
exit /b %LAYA_RESULTADO%
