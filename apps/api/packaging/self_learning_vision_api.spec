# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import cv2

block_cipher = None
repo_root = Path.cwd()
opencv_data = Path(cv2.data.haarcascades)

a = Analysis(
    ["desktop_launcher.py"],
    pathex=[str(repo_root)],
    binaries=[],
    datas=[(str(opencv_data), "cv2/data")],
    hiddenimports=[
        "app.main",
        "app.models",
        "app.api.auth",
        "app.services.face_detection",
        "app.services.recognition",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "mediapipe",
        "insightface",
        "onnxruntime",
        "celery",
        "redis",
        "pgvector",
        "asyncpg",
        "psycopg2",
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="slv-api-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
