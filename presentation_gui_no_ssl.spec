# -*- mode: python ; coding: utf-8 -*-
# Configuración de build para versión SIN VERIFICACIÓN SSL (SOLO PRUEBAS)
# NO USAR EN PRODUCCIÓN
#
# Esta versión establece la variable de entorno DISABLE_SSL_VERIFY_FOR_TESTING=true
# en tiempo de ejecución mediante un runtime hook

from pathlib import Path

block_cipher = None


added_files = [
    ('chapter_sync/inputs/Template.pptx', 'inputs'),
]
# Include .env file if it exists in the project root
env_path = Path('.env')
if env_path.exists():
    added_files.append(('.env', '.'))


hidden = [
    'matplotlib',
    'numpy',
    'pandas',
    'seaborn',
    'openpyxl',
    'pyarrow',
    'pptx',
    'PySide6',
    'PySide6.QtWidgets',
    'PySide6.QtGui',
    'PySide6.QtCore',
]


a = Analysis(
    ['chapter_sync/gui_qt/main.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=['runtime_hook_no_ssl.py'],
    excludes=[],
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],

    name='ChapterSync_NoSSL_Test',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

