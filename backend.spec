# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Roleplay Studio backend (onefile mode).

Builds the FastAPI + Hypercorn backend into a single executable
that Tauri can bundle as an external binary sidecar.
"""
import os
from pathlib import Path

# Project root — needed for PyInstaller to find api/ and app/ modules
_PROJECT_ROOT = os.getcwd()

# ── Block dangerous / too-large imports ───────────────────────
EXCLUDES = [
    "tkinter",
    "matplotlib",
    "scipy",
    "notebook",
    "jupyter",
    "IPython",
    "PIL.ImageShow",
    "PIL.ImageTk",
    "pandas",
    "tensorflow",
    "torch",
    "cv2",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "wx",
    "setuptools",
    "distutils",
    "pytest",
    "unittest",
]

# ── Hidden imports (modules PyInstaller can't auto-detect) ────
HIDDEN = [
    "hypercorn.asyncio",
    "hypercorn.config",
    "h2",
    "wsproto",
    "priority",
    "multidict",
    "chromadb.api.client",
    "chromadb.api.segment",
    "chromadb.db.duckdb",
    "chromadb.db.clickhouse",
    "chromadb.segment.distributed",
    "chromadb.telemetry",
    "chromadb.telemetry.product",
    "chromadb.telemetry.posthog",
    "chromadb.quota",
    "chromadb.rate_limiting",
    "chromadb.auth",
    "langchain_community",
    "langchain_openai",
    "langchain_chroma",
    "langchain_text_splitters",
    "langgraph",
    "langgraph.checkpoint",
    "langgraph.pregel",
    "langgraph.graph",
    "pypdf._writer",
    "pypdf._reader",
    "pypdf.constants",
    "docx",
    "PIL",
    "aiosqlite",
    "sqlalchemy.ext.asyncio",
    "sqlalchemy.dialects.sqlite",
    "httpx",
    "httpcore",
    "h11",
    "sniffio",
    "dotenv",
    "python_multipart",
    "yaml",
    "anyio",
    "anyio.streams.stapled",
    "dateutil",
    "tzdata",
    "orjson",
    "greenlet",
    "pydantic",
    "pydantic.deprecated.decorator",
    "pydantic._internal._config",
    "pydantic_settings",
    "chromadb.segment",
    "chromadb.segment.impl.manager.cache",
    "chromadb.quota.impl",
    "chromadb.rate_limiting.impl",
    "chromadb.auth.token",
    "chromadb.auth.token_transport",
]

a = Analysis(
    ["backend/run_backend.py"],
    pathex=[str(_PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="roleplay-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory=".",
)