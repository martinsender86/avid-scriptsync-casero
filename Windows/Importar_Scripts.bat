@echo off
chcp 65001 >nul
setlocal
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo No encuentro Python. Instalalo desde https://www.python.org/downloads/
  echo y marca la opcion "Add python.exe to PATH". Despues volve a abrir este archivo.
  pause
  exit /b 1
)
echo ============================================================
echo  IMPORTAR SCRIPTS POR LOTE  (Media Composer tiene que estar CERRADO)
echo ============================================================
echo.
%PY% "%~dp0Importar_Scripts.py" %*
echo.
pause
