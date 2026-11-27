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
if ! "$PY" -c "import avb" >/dev/null 2>&1; then
  echo "Primera vez: instalando pyavb..."
  "$PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1
  "$PY" -m pip install --quiet pyavb || { echo "No pude instalar pyavb (hace falta internet)."; read -r -p "Enter para cerrar..." _; exit 1; }
fi
echo "============================================================"
echo " SCRIPTSYNC: enlazar scripts con subclips (Media Composer CERRADO)"
echo "============================================================"
echo
"$PY" ScriptSync_Avid.py
echo
read -r -p "Enter para cerrar..." _
