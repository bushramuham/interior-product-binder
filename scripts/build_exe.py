"""Build the Windows GUI executable with PyInstaller.

Run from the repo root (inside the venv):
    python scripts/build_exe.py

Produces dist/DFH_Binder_Generator.exe — a single file that needs no Python
install. Place a .env (copied from .env.example) next to the exe to enable
webpage sources; binders built purely from PDF sources work without it.
"""

import os
import shutil
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
        dist = os.path.join(REPO_ROOT, "dist")
        exe = os.path.join(dist, "DFH_Binder_Generator.exe")
        print(f"\nBuilt: {exe} ({os.path.getsize(exe) / 1e6:.1f} MB)")
        # Ship a .env next to the exe: copy the repo's .env if present,
        # otherwise the .env.example template for the user to fill in.
        for candidate in (".env", ".env.example"):
            src = os.path.join(REPO_ROOT, candidate)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(dist, ".env"))
                print(f"Copied {candidate} -> dist/.env")
                break
        else:
            print("WARNING: no .env or .env.example found to copy into dist/")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
