# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Roleplay Studio backend.

Usage:
    pyinstaller backend/backend.spec --clean --noconfirm

Produces: dist/backend/backend (standalone binary)
"""

import os
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────
# PyInstaller exposes the absolute path to this .spec file as `SPEC`
# in the exec namespace. Using it (instead of __file__, which is NOT
# defined when PyInstaller does `exec(code, spec_namespace)`) keeps the
# spec portable across machines and CI runners.
SPEC_PATH = Path(SPEC).resolve()
PROJECT_ROOT = SPEC_PATH.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build" / "backend"

# ── ChromaDB persists at runtime, but needs data at build time ──────
# Ensure chroma_db dir exists so PyInstaller doesn't error on import
(PROJECT_ROOT / "chroma_db").mkdir(exist_ok=True)

# ── Blocklist: things we explicitly DON'T want bundled ───────────────
EXCLUDES = [
    # Test & dev
    "pytest",
    "ruff",
    "pre-commit",
    "black",
    "isort",
    "mypy",
    "coverage",
    # Not needed
    "tkinter",
    "matplotlib",
    "scipy",
    "pandas",
    "numpy.distutils",
    "PIL.ImageTk",
    "PIL.TkPhotoImage",
    "notebook",
    "ipython",
    "jupyter",
    "Cython",
    "setuptools",
    "wheel",
    "pip",
    # ChromaDB extras not needed
    "chromadb.cli",
    "chromadb.config",
    # ML frameworks not used
    "torch",
    "tensorflow",
    "transformers",
    "sentence_transformers",
]

# ── Hidden imports: things PyInstaller can't auto-detect ─────────────
HIDDEN_IMPORTS = [
    # ChromaDB & deps
    "chromadb",
    "chromadb.api",
    "chromadb.api.segment",
    "chromadb.api.fastapi",
    "chromadb.auth",
    "chromadb.db",
    "chromadb.telemetry",
    "chromadb.telemetry.product",
    "chromadb.utils",
    "chromadb.utils.embedding_functions",
    "chromadb.segment",
    "chromadb.segment.impl.vector",
    "chromadb.segment.impl.vector.hnswlib",
    "chromadb.segment.impl.metadata",
    "chromadb.segment.impl.manager.distributed",
    "chromadb.segment.impl.manager.local",
    # LangChain
    "langchain",
    "langchain_community",
    "langchain_community.embeddings",
    "langchain_community.chat_models",
    "langchain_core",
    "langchain_core.language_models",
    "langchain_core.embeddings",
    "langchain_core.prompts",
    "langchain_core.output_parsers",
    "langchain_core.messages",
    "langchain_core.runnables",
    "langchain_core.callbacks",
    "langchain_text_splitters",
    "langchain_chroma",
    "langchain_openai",
    "langgraph",
    "langgraph.graph",
    "langgraph.graph.message",
    "langgraph.checkpoint",
    "langgraph.pregel",
    # SQL & DB
    "sqlmodel",
    "sqlalchemy",
    "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm",
    "sqlalchemy.sql",
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    # Server
    "hypercorn",
    "hypercorn.asyncio",
    "hypercorn.config",
    "uvicorn.logging",
    "uvicorn.protocols",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "httptools",
    "wsproto",
    "h11",
    "h2",
    "priority",
    # FastAPI
    "fastapi",
    "fastapi.routing",
    "fastapi.openapi",
    "fastapi.openapi.utils",
    "fastapi.exception_handlers",
    "starlette",
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.staticfiles",
    "starlette.datastructures",
    "starlette.requests",
    "starlette.responses",
    "starlette.types",
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    "multipart",
    "python_multipart",
    # HTTP client
    "httpx",
    "httpcore",
    "httpcore._async",
    "httpcore._async.connection_pool",
    "h11._connection",
    # Utils
    "dotenv",
    "python_dotenv",
    "yaml",
    "orjson",
    "json",
    "asyncio",
    "logging",
    "uuid",
    "datetime",
    "pathlib",
    # File parsing
    "pypdf",
    "pypdf._reader",
    "pypdf._page",
    "docx",
    "docx.text",
    "docx.document",
    # Template engine
    "jinja2",
    "markupsafe",
    # AIO & asyncio deps
    "anyio",
    "sniffio",
    "idna",
    "certifi",
    "charset_normalizer",
    "urllib3",
    # Stdlib modules that PyInstaller fails to detect when imported
    # transitively from a bundled package (chromadb.config pulls
    # `graphlib` from stdlib and the import goes missing at runtime).
    "graphlib",
    "sqlite3",
    # Lazy / dynamic imports that PyInstaller's static analyser misses:
    # - `aiosqlite`: SQLAlchemy's async SQLite dialect does
    #   `__import__("aiosqlite")` inside a dialect module, so the
    #   dependency graph never sees it.
    "aiosqlite",
]

# ── Data files to bundle ─────────────────────────────────────────────
# ChromaDB needs to find its native libs and migrations.
# Migration location changed across versions:
#   - < 1.5 : chromadb/db/migrations/   (nested)
#   - >=1.5 : chromadb/migrations/      (flattened)
# We try the new location first, fall back to the old one.
import chromadb

_CHROMA_DIR = Path(chromadb.__file__).resolve().parent
_MIGRATIONS_CANDIDATES = [
    _CHROMA_DIR / "migrations",          # >= 1.5
    _CHROMA_DIR / "db" / "migrations",  # <  1.5
]
_MIGRATIONS_SRC = next(
    (p for p in _MIGRATIONS_CANDIDATES if p.exists()),
    _MIGRATIONS_CANDIDATES[0],  # fall back silently so PyInstaller errors clearly
)

# Alembic artifacts live at the repo root and are resolved by
# SqlAlchemyStore.init_db() relative to its own source file (4 levels
# up). Inside the onedir bundle, that points to .../_internal/, so we
# place alembic.ini and the alembic/ tree there.
_ALEMBIC_INI_SRC = PROJECT_ROOT / "alembic.ini"
_ALEMBIC_DIR_SRC = PROJECT_ROOT / "alembic"

DATAS = [
    (
        str(_MIGRATIONS_SRC),
        "chromadb/db/migrations",
    ),
    # NOTE: we deliberately do NOT use the dest names "alembic.ini" and
    # "alembic" here. PyInstaller treats any bundled Python package
    # (`alembic`) and any `datas` entry with the same name as the same
    # destination, and stores the additional data as an overlay
    # directory (e.g. `_internal/alembic.ini/alembic.ini`) that the
    # `AlembicConfig` loader can't read. Routing them through a
    # `migrations/` subdirectory avoids the conflict.
    (
        str(_ALEMBIC_INI_SRC),
        "migrations/alembic.ini",
    ),
    (
        str(_ALEMBIC_DIR_SRC),
        "migrations/alembic",
    ),
]

# ── PyInstaller requires key imports to be explicitly collected ──
# Some libs (langchain, chromadb) register plugins dynamically
import importlib.metadata as _md

# In PyInstaller 6.x, `collect_all` returns (datas, binaries,
# hiddenimports) where inner entries are *raw* 2-tuples `(src, dest)`.
# `Analysis.__init__` knows how to normalize these — including
# expanding directories (e.g. `*.dist-info`) into individual files —
# but ONLY when we hand them in via the `datas=` / `binaries=` /
# `hiddenimports=` kwargs at construction time. Mutating `a.datas` /
# `a.binaries` afterwards bypasses that normalization and trips
# downstream `IsADirectoryError` / "not enough values to unpack".
from PyInstaller.utils.hooks import collect_all as _collect_all

# Use a `from` import to avoid shadowing the top-level `PyInstaller`
# module that PyInstaller itself injects for `Analysis`/`EXE`/
# `COLLECT` to work.

COLLECT_ALL = []
_EXTRA_DATAS = []
_EXTRA_BINARIES = []
_EXTRA_HIDDENIMPORTS = []
for pkg in [
    "langchain",
    "langchain_community",
    "langchain_core",
    "langchain_openai",
    "langchain_chroma",
    "langchain_text_splitters",
    "langgraph",
    "chromadb",
    "httpx",
    "httpcore",
    "sqlalchemy",
    "hypercorn",
    "starlette",
    "fastapi",
]:
    try:
        dist = _md.distribution(pkg)
        COLLECT_ALL.append(pkg)
        print(f"  ✓ Will collect: {pkg} ({dist.version})")
    except _md.PackageNotFoundError:
        print(f"  ✗ Package not found: {pkg}")
        continue
    try:
        _d, _b, _h = _collect_all(pkg)
        _EXTRA_DATAS += _d
        _EXTRA_BINARIES += _b
        _EXTRA_HIDDENIMPORTS += _h
    except Exception as e:
        print(f"  ! collect_all({pkg}) failed: {e}")

# Merge extras with the manual migrations entry. Analysis will normalize
# (dest_name, src_name) and expand directory entries.
DATAS = DATAS + _EXTRA_DATAS
BINARIES = _EXTRA_BINARIES
HIDDEN_IMPORTS = HIDDEN_IMPORTS + _EXTRA_HIDDENIMPORTS

# ── PyInstaller block_cipher ─────────────────────────────────────────
block_cipher = None

# ── Analysis ─────────────────────────────────────────────────────────
a = Analysis(
    [str(BACKEND_DIR / "run_backend.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=BINARIES,
    datas=DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── PYZ ──────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE (onefile) ────────────────────────────────────────────────────
# PyInstaller 6.x onefile pattern: include all binaries, zipped data,
# and datas directly in the EXE. No COLLECT — the result is a single
# self-extracting `dist/roleplay-backend` file. Tauri's sidecar
# resources look up `roleplay-backend-<triple>` as a single file, not
# a directory, so onedir would not work.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="roleplay-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Show terminal for debugging; Tauri parent reads stdout/stderr via pipes regardless
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)