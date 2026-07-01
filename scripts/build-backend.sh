#!/bin/bash
set -euo pipefail

# ── Build the Roleplay Studio backend into a standalone binary ──
# Produces frontend/src-tauri/binaries/roleplay-backend-<triple>
# which Tauri bundles as a resource sidecar.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BINARIES_DIR="$PROJECT_ROOT/frontend/src-tauri/binaries"

echo "🔧 Building Roleplay Studio backend with PyInstaller..."
echo "   Project root: $PROJECT_ROOT"
echo "   Output:       $BINARIES_DIR"

# ── Detect Tauri triple ───────────────────────────────────────
ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    TRIPLE="aarch64-apple-darwin"
elif [ "$ARCH" = "x86_64" ]; then
    TRIPLE="x86_64-apple-darwin"
else
    echo "❌ Unknown architecture: $ARCH"
    exit 1
fi

mkdir -p "$BINARIES_DIR"
cd "$PROJECT_ROOT"

# ── Clean previous build ──────────────────────────────────────
rm -rf build dist backend.spec.lock
rm -f "$BINARIES_DIR/roleplay-backend-$TRIPLE"

# ── Run PyInstaller (onefile mode) ────────────────────────────
.venv/bin/python -m PyInstaller --clean --noconfirm backend/run_backend.spec 2>&1

echo ""
echo "✅ PyInstaller build complete!"

# ── Copy single binary to Tauri's binaries dir ────────────────
cp dist/roleplay-backend "$BINARIES_DIR/roleplay-backend-$TRIPLE"
chmod +x "$BINARIES_DIR/roleplay-backend-$TRIPLE"

echo ""
echo "📦 Binary ready: $BINARIES_DIR/roleplay-backend-$TRIPLE"
echo ""
echo "To build the macOS .app:"
echo "  cd frontend && npx tauri build"
echo ""

# ── Show size ─────────────────────────────────────────────────
SIZE="$(du -sh "$BINARIES_DIR/roleplay-backend-$TRIPLE" | cut -f1)"
echo "   Size: $SIZE"