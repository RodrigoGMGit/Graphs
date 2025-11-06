# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


added_files = [
    ('chapter_sync/inputs/Template.pptx', 'inputs'),
]

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
    runtime_hooks=[],
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

    name='ChapterSync PPT Generator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
