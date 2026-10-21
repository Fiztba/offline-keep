"""Build a single-file Windows executable with PyInstaller: python packaging/build_exe.py"""
from pathlib import Path

import PyInstaller.__main__

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

PyInstaller.__main__.run([
    str(ROOT / "Offline Keep.pyw"),
    "--name", "OfflineKeep",
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--distpath", str(HERE / "dist"),
    "--workpath", str(HERE / "build"),
    "--specpath", str(HERE / "build"),
    "--paths", str(ROOT),
])
