# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Star Citizen Mining Overlay.
Build with:  pyinstaller overlay.spec
Output:      dist\MiningOverlay\MiningOverlay.exe  (one-folder bundle)
"""

import sys
from pathlib import Path
import torch

ROOT = Path(SPECPATH)
TORCH_DIR = Path(torch.__file__).parent

block_cipher = None

a = Analysis(
    [str(ROOT / 'overlay.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Model + templates + fonts
        (str(ROOT / 'data' / 'digit_cnn.pt'),         'data'),
        (str(ROOT / 'data' / 'digit_templates'),       'data/digit_templates'),
        (str(ROOT / 'data' / 'fonts'),                 'data/fonts'),
        # Torch lib DLLs (CUDA build ships many .dll files)
        (str(TORCH_DIR / 'lib'), 'torch/lib'),
    ],
    hiddenimports=[
        # pystray win32 backend
        'pystray._win32',
        # supabase / httpx internals
        'httpx._transports.default',
        'anyio._backends._asyncio',
        # torch
        'torch',
        'torch.nn',
        'torch.nn.functional',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'unittest', 'xmlrpc', 'email', 'html', 'http.server',
        'IPython', 'matplotlib', 'pandas', 'scipy',
        'torchvision', 'torchaudio',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MiningOverlay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    # Require administrator rights (needed for global keyboard hook)
    uac_admin=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MiningOverlay',
)
