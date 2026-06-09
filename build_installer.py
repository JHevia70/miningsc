"""
Build script: PyInstaller → Inno Setup → web/private/MiningScanner.zip

Usage:
    python build_installer.py

Steps:
    1. Run PyInstaller with scanner.spec
    2. Install Inno Setup silently if not found
    3. Compile installer.iss → MiningScanner_Setup.exe
    4. Zip the installer → web/private/MiningScanner.zip  (served by the API route)
"""

import subprocess
import sys
import shutil
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT        = Path(__file__).parent
DIST_DIR    = Path(r"F:\SC_temp\dist\MiningScanner")
BUILD_DIR   = Path(r"F:\SC_temp\build")
INSTALL_DIR = Path(r"F:\SC_temp\installer")
WEB_PRIVATE = ROOT / "web" / "private"

ISCC_PATHS = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\iscc.exe"),
    Path(r"C:\Program Files\Inno Setup 6\iscc.exe"),
]
INNO_INSTALLER_URL = "https://jrsoftware.org/download.php/is.exe"
INNO_INSTALLER_TMP = Path(r"F:\SC_temp\innosetup-installer.exe")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def run(cmd: list[str], **kwargs):
    print(f"\n>>> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"[ERROR] command failed with code {result.returncode}")
        sys.exit(result.returncode)

def find_iscc() -> Path | None:
    for p in ISCC_PATHS:
        if p.exists():
            return p
    # Also check PATH
    found = shutil.which("iscc")
    return Path(found) if found else None

def install_inno():
    print("\n[INFO] Inno Setup not found — downloading installer...")
    INNO_INSTALLER_TMP.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(INNO_INSTALLER_URL, INNO_INSTALLER_TMP)
    print(f"[INFO] Installing Inno Setup silently from {INNO_INSTALLER_TMP}...")
    run([
        str(INNO_INSTALLER_TMP),
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
        "/SP-",
    ])

# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
GPU_DLLS = [
    "onnxruntime_providers_cuda.dll",
    "onnxruntime_providers_tensorrt.dll",
    "onnxruntime_providers_rocm.dll",
]

def step_pyinstaller():
    print("\n=== Step 1: PyInstaller ===")
    DIST_DIR.parent.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    run([
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "scanner.spec"),
        "--distpath", str(DIST_DIR.parent),
        "--workpath", str(BUILD_DIR),
        "--noconfirm",
    ], cwd=str(ROOT))

    # Strip GPU-only onnxruntime DLLs — not needed, saves ~300 MB
    # (newer onnxruntime versions may not include them at all — skip if absent)
    ort_capi = DIST_DIR / "_internal" / "onnxruntime" / "capi"
    for dll in GPU_DLLS:
        p = ort_capi / dll
        if p.exists():
            size_mb = p.stat().st_size // 1024 // 1024
            p.unlink()
            print(f"[OK] Stripped {dll} ({size_mb} MB)")
        else:
            print(f"[OK] {dll} not present (already excluded)")

    size_mb = sum(f.stat().st_size for f in DIST_DIR.rglob("*") if f.is_file()) // 1024 // 1024
    print(f"[OK] PyInstaller output: {DIST_DIR} ({size_mb} MB)")

def step_inno():
    print("\n=== Step 2: Inno Setup ===")
    iscc = find_iscc()
    if iscc is None:
        install_inno()
        iscc = find_iscc()
    if iscc is None:
        print("[ERROR] Could not find iscc.exe after install. Add Inno Setup to PATH.")
        sys.exit(1)

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    run([str(iscc), str(ROOT / "installer.iss")])
    setup_exe = INSTALL_DIR / "MiningScanner_Setup.exe"
    print(f"[OK] Installer: {setup_exe} ({setup_exe.stat().st_size // 1024 // 1024} MB)")
    return setup_exe

def step_zip(setup_exe: Path):
    print("\n=== Step 3: Package for web ===")
    WEB_PRIVATE.mkdir(parents=True, exist_ok=True)
    zip_path = WEB_PRIVATE / "MiningScanner.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(setup_exe, "MiningScanner_Setup.exe")
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"[OK] Web package: {zip_path} ({size_mb:.1f} MB)")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    step_pyinstaller()
    setup_exe = step_inno()
    step_zip(setup_exe)
    print("\n=== Done ===")
    print(f"  Installer : {INSTALL_DIR / 'MiningScanner_Setup.exe'}")
    print(f"  Web zip   : {WEB_PRIVATE / 'MiningScanner.zip'}")
    print("\nDeploy the web app to make the download available.")
