#!/bin/bash
# Usa un Python propio en ~/.avid_scripts/venv (no toca el Python del sistema)
cd "$(dirname "$0")" || exit 1
VENV="$HOME/.avid_scripts/venv"
if [ ! -x "$VENV/bin/python" ]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "No encuentro Python 3. Instalalo desde https://www.python.org/downloads/ y volve a abrir este archivo."
    read -r -p "Enter para cerrar..." _; exit 1
  fi
  echo "Primera vez: preparando Python en $VENV ..."
  mkdir -p "$HOME/.avid_scripts"
  python3 -m venv "$VENV" || { echo "No pude crear el entorno de Python."; read -r -p "Enter para cerrar..." _; exit 1; }
fi
PY="$VENV/bin/python"
echo "============================================================"
echo " IMPORTAR SCRIPTS POR LOTE  (Media Composer tiene que estar CERRADO)"
echo "============================================================"
echo
"$PY" Importar_Scripts.py
echo
read -r -p "Enter para cerrar..." _
