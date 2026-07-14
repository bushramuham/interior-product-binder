"""Build the Windows GUI executable with PyInstaller.

Run from the repo root (inside the venv):
    python scripts/build_exe.py

Produces dist/DFH_Binder_Generator.exe — a single file that needs no Python
install. Place a .env (copied from .env.example) next to the exe to enable
webpage sources; binders built purely from PDF sources work without it.
"""

import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    os.chdir(REPO_ROOT)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "DFH_Binder_Generator",
        "--add-data", f"assets{os.pathsep}assets",  # dfh logo
        "--clean",
        "--noconfirm",
        "gui.py",
    ]
    print(" ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode == 0:
        exe = os.path.join(REPO_ROOT, "dist", "DFH_Binder_Generator.exe")
        print(f"\nBuilt: {exe} ({os.path.getsize(exe) / 1e6:.1f} MB)")
        print("Ship it together with a .env file (see .env.example).")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
