#!/usr/bin/env bash
# ── Install Roleplay Studio.app from an unsigned .dmg ──
#
# Strips the Gatekeeper quarantine flag from the bundled .app before
# copying it to /Applications, so end users don't have to fight the
# "developer cannot be verified" dialog on first launch. This is the
# Option B companion to the ad-hoc-signed .dmg that
# `scripts/build-backend.sh` + `tauri build` produce — see
# docs/superpowers/specs/2026-06-06-macos-build-gotchas.md for context
# (Distribution without Apple Developer ID).
#
# Usage:
#   ./scripts/install.sh path/to/Roleplay\ Studio_0.1.0_aarch64.dmg
#   ./scripts/install.sh path/to/Roleplay\ Studio_0.1.0_aarch64.dmg --to ~/Applications
#   ./scripts/install.sh path/to/Roleplay\ Studio_0.1.0_aarch64.dmg --force
#
# Exit codes:
#   0  success
#   1  user error (bad args, missing file, .app not found in dmg)
#   2  system error (hdiutil / cp / xattr failure)

set -euo pipefail

print_usage() {
    cat <<EOF
Usage: $0 <path-to-dmg> [--to <install-dir>] [--force]

Arguments:
  <path-to-dmg>          Path to the .dmg produced by \`tauri build\`.

Options:
  --to <dir>             Install directory (default: /Applications)
  --force                Overwrite an existing Roleplay Studio.app
  -h, --help             Show this help

Examples:
  $0 "Roleplay Studio_0.1.0_aarch64.dmg"
  $0 ~/Downloads/roleplay.dmg --to ~/Applications --force
EOF
}

# ── Defaults ───────────────────────────────────────────────────────
DMG=""
INSTALL_DIR="/Applications"
FORCE=""

# ── Parse args ─────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            print_usage
            exit 0
            ;;
        --to)
            if [ $# -lt 2 ]; then
                echo "❌ --to requires a directory argument" >&2
                print_usage >&2
                exit 1
            fi
            INSTALL_DIR="$2"
            shift 2
            ;;
        --force)
            FORCE="1"
            shift
            ;;
        -*)
            echo "❌ Unknown option: $1" >&2
            print_usage >&2
            exit 1
            ;;
        *)
            if [ -n "$DMG" ]; then
                echo "❌ Multiple .dmg paths given; expected exactly one." >&2
                print_usage >&2
                exit 1
            fi
            DMG="$1"
            shift
            ;;
    esac
done

# ── Validate inputs ────────────────────────────────────────────────
if [ -z "$DMG" ]; then
    echo "❌ No .dmg path provided." >&2
    print_usage >&2
    exit 1
fi

if [ ! -f "$DMG" ]; then
    echo "❌ File not found: $DMG" >&2
    exit 1
fi

# Strip quarantine on the .dmg itself too, in case the user downloaded
# it via a browser (which is the typical flow). This is a no-op if
# the flag is already absent.
xattr -d com.apple.quarantine "$DMG" 2>/dev/null || true

# ── Mount the .dmg (read-only, no browse, no verify) ──────────────
echo "📀 Mounting $(basename "$DMG")…"
MOUNT_OUTPUT="$(hdiutil attach -nobrowse -noverify -readonly "$DMG" 2>&1)" || {
    echo "❌ Failed to mount .dmg:" >&2
    echo "$MOUNT_OUTPUT" >&2
    exit 2
}
# hdiutil emits tab-separated lines like:
#   /dev/disk4s1  Apple_HFS  /Volumes/Roleplay Studio
# The mount point is the THIRD tab-separated field — but `awk '{print
# $NF}'` doesn't work here because the path itself can contain spaces
# ("Roleplay Studio") and $NF stops at the first whitespace boundary.
# `cut -f3-` takes the whole tail of the line from the 3rd field
# onwards, which is the exact mount path.
MOUNT_POINT="$(printf '%s\n' "$MOUNT_OUTPUT" | grep '/Volumes/' | cut -f3- | head -n 1)"
if [ -z "$MOUNT_POINT" ] || [ ! -d "$MOUNT_POINT" ]; then
    echo "❌ Could not parse mount point from hdiutil output:" >&2
    echo "$MOUNT_OUTPUT" >&2
    exit 2
fi
echo "   Mounted at: $MOUNT_POINT"

# Ensure we always detach, even on failure.
cleanup() {
    if [ -n "${MOUNT_POINT:-}" ]; then
        hdiutil detach "$MOUNT_POINT" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

# ── Locate the .app bundle inside the mounted image ────────────────
APP_SRC=""
STAGE_DIR=""
# Look for any *.app at the top of the mount point first.
for candidate in "$MOUNT_POINT"/*.app; do
    if [ -d "$candidate" ]; then
        APP_SRC="$candidate"
        break
    fi
done

# Fall back to a recursive search (some .dmg layouts nest the .app).
if [ -z "$APP_SRC" ]; then
    APP_SRC="$(find "$MOUNT_POINT" -maxdepth 3 -name '*.app' -type d | head -n 1 || true)"
fi

if [ -z "$APP_SRC" ] || [ ! -d "$APP_SRC" ]; then
    echo "❌ No .app bundle found inside the .dmg." >&2
    echo "   Mount point contents:" >&2
    ls -la "$MOUNT_POINT" >&2
    exit 1
fi
APP_NAME="$(basename "$APP_SRC")"
echo "📦 Found: $APP_NAME"

# ── Stage the .app to a writable temp dir, strip quarantine, then ───
# install. The .dmg is mounted read-only, so we can't `xattr` on the
# mount itself. Copy → strip → move gives us the right behaviour
# without remounting read-write.
STAGE_DIR="$(mktemp -d -t roleplay-studio-install)"
echo "📋 Staging to ${STAGE_DIR}…"
cp -R "$APP_SRC" "${STAGE_DIR}/$APP_NAME"

# Detach the .dmg now that we have a copy — saves the user from a
# stray Finder window popping up later.
cleanup
trap - EXIT

# Strip the quarantine flag recursively from the staged copy. Each
# bundled binary gets its own flag; -r is required.
echo "🛡  Stripping quarantine flag…"
xattr -dr com.apple.quarantine "${STAGE_DIR}/$APP_NAME"

# ── Install to target directory ────────────────────────────────────
mkdir -p "$INSTALL_DIR"
DEST="$INSTALL_DIR/$APP_NAME"

if [ -e "$DEST" ] || [ -L "$DEST" ]; then
    if [ -n "$FORCE" ]; then
        echo "🗑  Removing existing $DEST (--force)"
        rm -rf "$DEST"
    else
        echo "❌ $DEST already exists. Re-run with --force to overwrite." >&2
        rm -rf "${STAGE_DIR}"
        exit 1
    fi
fi

echo "📥 Installing to ${DEST}…"
mv "${STAGE_DIR}/$APP_NAME" "$DEST"
rmdir "${STAGE_DIR}" 2>/dev/null || true

# ── Done ───────────────────────────────────────────────────────────
echo ""
echo "✅ Installed to $DEST"
echo ""
echo "Next steps:"
echo "  • Launch:    open \"$DEST\""
echo "  • Or double-click in Finder"
echo ""
echo "The app is ad-hoc signed, so macOS may still prompt for an"
echo "explicit confirmation on first launch. If it does, right-click"
echo "the .app in Finder → Open → Open. After that, normal launch works."
