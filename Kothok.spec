# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Kothok (কথক). Build with:  .\build-portable.ps1
# (old spec kept in legacy/BanglaVoiceToText_v1.spec)
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("customtkinter") + [("app.ico", ".")]
binaries = collect_dynamic_libs("sherpa_onnx") + collect_dynamic_libs("sounddevice") + collect_dynamic_libs("_sounddevice_data")

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=["pystray._win32", "PIL._tkinter_finder", "sherpa_onnx", "customtkinter"],
    excludes=["matplotlib", "scipy", "pandas", "IPython", "pytest", "numpy.f2py", "pypinyin", "sentencepiece"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Kothok",
    icon="app.ico",
    version="version_info.txt",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Kothok")
