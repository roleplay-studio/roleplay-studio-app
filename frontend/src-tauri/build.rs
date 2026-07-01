fn main() {
    // If the real PyInstaller binary isn't present (dev mode), create a
    // launcher script that runs `uv run hypercorn` from the project root.
    // The real binary overwrites this when scripts/build-backend.sh runs.
    let out_dir = std::path::PathBuf::from(
        std::env::var("CARGO_MANIFEST_DIR").unwrap(),
    )
    .join("binaries");

    let triple = std::env::var("TAURI_ENV_TARGET_TRIPLE")
        .unwrap_or_else(|_| "aarch64-apple-darwin".into());

    let binary_path = out_dir.join(format!("roleplay-backend-{triple}"));

    if !binary_path.exists() {
        std::fs::create_dir_all(&out_dir).ok();

        // Launcher script — forwards to `uv run hypercorn` from project root.
        // Replaced by scripts/build-backend.sh for release builds.
        let launcher = format!(
            r#"#!/bin/bash
# Placeholder — replaced by build-backend.sh for release
cd "$(dirname "$0")/../.." || exit 1
exec uv run hypercorn api.main:app --bind 127.0.0.1:55245
"#
        );
        std::fs::write(&binary_path, launcher.as_bytes()).ok();

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&binary_path, PermissionsExt::from_mode(0o755)).ok();
        }

        println!("cargo:warning=Created dev launcher at {:?}", binary_path);
        println!("cargo:warning=  → For release, run scripts/build-backend.sh");
    }

    tauri_build::build()
}