#!/usr/bin/env bash
# build.sh - Compila la aplicación Graphs usando PyInstaller.
# Requiere Python 3 y PyInstaller instalado.

set -euo pipefail

# Instala dependencias
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Ejecuta PyInstaller usando la spec incluida

pyinstaller presentation_gui.spec

