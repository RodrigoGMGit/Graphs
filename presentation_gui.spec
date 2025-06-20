# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


added_files = [
    ('files', 'files'),
    ('inputs/Template.pptx', 'inputs'),
    ('generate_presentation.py', '.')
]

hidden = [
    'matplotlib',
    'numpy',
    'pandas',
    'seaborn',
    'openpyxl',
    'pyarrow',
    'pptx',
    'dearpygui.dearpygui',
]


a = Analysis(
    ['presentation_gui.py'],
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
    console=True,
)
