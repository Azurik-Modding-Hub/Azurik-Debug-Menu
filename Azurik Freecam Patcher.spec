# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['patcher.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/studio.ico', 'assets'),
           ('freecam/laboratory-catalogue.json', 'freecam')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Azurik Freecam Patcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='assets/windows-version.txt',
    icon=['assets/studio.ico'],
)
