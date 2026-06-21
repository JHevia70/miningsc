# -*- mode: python ; coding: utf-8 -*-
# Build: python build_installer.py
# Manual: pyinstaller scanner.spec --distpath F:/SC_temp/dist --workpath F:/SC_temp/build --noconfirm

from pathlib import Path
import site

ROOT = Path(SPECPATH)

# Locate rapidocr_onnxruntime package (ONNX models + config YAMLs must be bundled)
def _find_pkg(name):
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        p = Path(sp) / name
        if p.exists():
            return p
    raise FileNotFoundError(f"Package not found: {name}")

RAPIDOCR_DIR = _find_pkg('rapidocr_onnxruntime')

block_cipher = None

a = Analysis(
    [str(ROOT / 'overlay.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'data' / 'digit_cnn.onnx'),     'data'),
        (str(ROOT / 'data' / 'digit_templates'),     'data/digit_templates'),
        (str(ROOT / 'data' / 'fonts'),               'data/fonts'),
        # RapidOCR: ONNX detection/recognition models and config files
        (str(RAPIDOCR_DIR / 'models'),               'rapidocr_onnxruntime/models'),
        (str(RAPIDOCR_DIR / 'config.yaml'),          'rapidocr_onnxruntime'),
        (str(RAPIDOCR_DIR / 'ch_ppocr_v2_cls'),     'rapidocr_onnxruntime/ch_ppocr_v2_cls'),
        (str(RAPIDOCR_DIR / 'ch_ppocr_v3_det'),     'rapidocr_onnxruntime/ch_ppocr_v3_det'),
        (str(RAPIDOCR_DIR / 'ch_ppocr_v3_rec'),     'rapidocr_onnxruntime/ch_ppocr_v3_rec'),
    ],
    hiddenimports=[
        'pystray._win32',
        'httpx._transports.default',
        'anyio._backends._asyncio',
        'onnxruntime',
        'rapidocr_onnxruntime',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy ML frameworks not needed at runtime
        'torch', 'torchvision', 'torchaudio',
        'tensorflow', 'keras',
        # onnxruntime GPU providers (we use CPUExecutionProvider only)
        'onnxruntime.capi.onnxruntime_providers_cuda',
        'onnxruntime.capi.onnxruntime_providers_tensorrt',
        'onnxruntime.capi.onnxruntime_providers_rocm',
        # Unused data-science stack that gets pulled transitively
        'pyarrow', 'pandas', 'scipy', 'grpc',
        'IPython', 'matplotlib',
        # Unused stdlib
        'unittest', 'xmlrpc', 'http.server',
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
    name='MiningScanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MiningScanner',
)
