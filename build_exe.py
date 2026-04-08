#!/usr/bin/env python3
"""
Build script to create the PC Check EXE using PyInstaller.
Run: python build_exe.py
"""

import subprocess
import sys
import os
import shutil

def main():
    print("PC Check EXE Builder")
    print("=" * 40)

    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print("[OK] PyInstaller installed")
    except ImportError:
        print("[INFO] Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Clean previous builds
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")

    print("\nBuilding EXE (this may take a minute)...\n")

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",           # Single EXE file
        "--noconsole",         # No console window (hide CMD)
        "--name", "PCCheck",
        "--add-data", "webhook_url.txt;.",  # Include URL file
        "pc_check_exe.py"
    ]

    result = subprocess.call(cmd)

    if result == 0:
        print("\n" + "=" * 40)
        print("SUCCESS! EXE created at: dist/PCCheck.exe")
        print("=" * 40)
    else:
        print("\n[ERROR] Build failed!")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
