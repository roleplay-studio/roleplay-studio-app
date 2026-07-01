use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::Manager;

const BACKEND_PORT: &str = "55245";

struct BackendProcess(Mutex<Option<Child>>);

/// Kill any lingering Python/hypercorn process on the backend port.
fn kill_backend_processes() {
    let _ = Command::new("sh")
        .args([
            "-c",
            &format!(
                "lsof -ti :{port} | xargs kill -9 2>/dev/null; pkill -9 -f hypercorn 2>/dev/null; pkill -9 -f roleplay-backend 2>/dev/null; true",
                port = BACKEND_PORT
            ),
        ])
        .output();
}

/// Find the PyInstaller-built backend binary.
///
/// Order of resolution:
///   1. Resource dir (within .app bundle) — release mode
///   2. Dev binaries directory — for local testing without bundling
///   3. Fallback to `uv run hypercorn` — plain dev mode
fn find_backend_binary(app: &tauri::App) -> Option<PathBuf> {
    // 1. Inside .app bundle: Resources/backend/roleplay-backend-<triple>
    if let Ok(resource_dir) = app.path().resource_dir() {
        let triple = detect_triple().unwrap_or_else(|_| "aarch64-apple-darwin".into());
        let bundle_path = resource_dir
            .join("backend")
            .join(format!("roleplay-backend-{triple}"));
        log::info!(
            "Looking for backend bundle at: {:?} (exists: {})",
            bundle_path,
            bundle_path.exists()
        );
        if bundle_path.exists() {
            log::info!("Found bundled backend: {:?}", bundle_path);
            return Some(bundle_path);
        }
    } else {
        log::warn!("Could not get resource_dir");
    }

    // 2. Also try app path relative (from inside .app bundle)
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            // The bundle dir where the MacOS binary lives
            let bundle_path = exe_dir
                .parent()
                .map(|p| p.join("Resources"))
                .unwrap_or(exe_dir.to_path_buf())
                .join("backend")
                .join(format!("roleplay-backend-{}", detect_triple().unwrap_or_else(|_| "aarch64-apple-darwin".into())));
            log::info!(
                "Trying bundle path from exe: {:?} (exists: {})",
                bundle_path,
                bundle_path.exists()
            );
            if bundle_path.exists() {
                log::info!("Found bundled backend at exe-relative path");
                return Some(bundle_path);
            }
        }
    }

    // 2. Dev binaries directory (frontend/src-tauri/binaries/)
    if let Ok(cwd) = std::env::current_dir() {
        let triple = detect_triple().unwrap_or_else(|_| "aarch64-apple-darwin".into());
        let dev_path = cwd
            .join("binaries")
            .join(format!("roleplay-backend-{triple}"));
        if dev_path.exists() {
            log::info!("Found dev backend binary: {:?}", dev_path);
            return Some(dev_path);
        }
        let dev_path2 = cwd
            .join("frontend")
            .join("src-tauri")
            .join("binaries")
            .join(format!("roleplay-backend-{triple}"));
        if dev_path2.exists() {
            log::info!("Found dev backend binary: {:?}", dev_path2);
            return Some(dev_path2);
        }
    }

    None
}

fn detect_triple() -> Result<String, std::env::VarError> {
    match (std::env::consts::ARCH, std::env::consts::OS) {
        ("aarch64", "macos") => Ok("aarch64-apple-darwin".into()),
        ("x86_64", "macos") => Ok("x86_64-apple-darwin".into()),
        _ => Err(std::env::VarError::NotPresent),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            // Enable logging (debug only — plugin may not be bundled in release)
            #[cfg(debug_assertions)]
            app.handle().plugin(
                tauri_plugin_log::Builder::default()
                    .level(log::LevelFilter::Info)
                    .build(),
            )?;

            // Kill any leftover backend from a previous run

            // Skip spawning a bundled backend if another process is already
            // listening on the backend port. ``make dev`` starts the
            // dev ``run_backend.py`` on 55245 first, then runs ``make
            // dev-tauri``; if we spawn a bundled backend too they race
            // for the same port and one dies with ``OSError: [Errno
            // 48] Address already in use``. Detecting the live port up
            // front lets us reuse the existing backend (which already
            // has the right ``.env`` and dev mode) without a fight.
            // See docs/review.md (Tauri-bundle-env-forwarding) for
            // context.
            let port_in_use = std::net::TcpStream::connect_timeout(
                &format!("127.0.0.1:{BACKEND_PORT}").parse().unwrap(),
                std::time::Duration::from_millis(100),
            )
            .is_ok();
            if port_in_use {
                log::info!(
                    "Port {port} already in use — skipping bundled-backend spawn (assuming dev backend is up)",
                    port = BACKEND_PORT
                );
                app.manage(BackendProcess(Mutex::new(None)));
                return Ok(());
            }

            let child = match find_backend_binary(app) {
                // Option A: PyInstaller sidecar binary
                Some(binary_path) => {
                    log::info!("Starting bundled backend: {:?}", binary_path);
                    // DEBUG-FIX-TAURI-ENV: explicitly forward the dev-mode
                    // env vars from the parent Tauri process to the
                    // bundled Python backend. ``Command::new().spawn()``
                    // inherits the parent's env by default, but in the
                    // ``tauri dev`` chain (``make -> npx -> cargo run ->
                    // target/debug/app``) the env gets stripped somewhere
                    // along the way, so the bundled backend never sees
                    // ``DEBUG=true`` set by ``make dev-debug``. Forwarding
                    // them explicitly makes the bundled backend behave the
                    // same as the dev ``run_backend.py`` process and keeps
                    // the LLM debug modal available in dev.
                    let mut cmd = Command::new(&binary_path);
                    cmd.stdout(Stdio::inherit()).stderr(Stdio::inherit());
                    for key in ["DEBUG", "ENVIRONMENT"] {
                        if let Ok(value) = std::env::var(key) {
                            log::info!("Forwarding {key}={value} to bundled backend");
                            cmd.env(key, value);
                        }
                    }
                    cmd.spawn()
                        .map_err(|e| {
                            log::warn!("Could not start bundled backend: {e}");
                            e
                        })
                        .ok()
                }
                // Option B: Dev mode — uv run hypercorn
                None => {
                    let project_root = std::env::current_dir()
                        .unwrap_or_default()
                        .parent()
                        .map(|p| p.to_path_buf())
                        .unwrap_or_default();

                    log::info!(
                        "No bundled backend found — starting via `uv run hypercorn` from {project_root:?}",
                    );

                    Command::new("uv")
                        .args([
                            "run",
                            "hypercorn",
                            "api.main:app",
                            "--bind",
                            &format!("127.0.0.1:{BACKEND_PORT}"),
                        ])
                        .current_dir(&project_root)
                        // DEBUG-FIX-TAURI-ENV: same env-forwarding as the
                        // bundled-backend branch above. Without this the
                        // dev-fallback path silently drops DEBUG/ENVIRONMENT
                        // and the user sees "production mode" when they
                        // launched via ``make dev-debug``.
                        .envs(
                            ["DEBUG", "ENVIRONMENT"]
                                .into_iter()
                                .filter_map(|k| std::env::var(k).ok().map(|v| (k, v))),
                        )
                        .spawn()
                        .map_err(|e| {
                            log::warn!(
                                "Could not start backend via uv: {e}. \
                                 Run manually: uv run hypercorn api.main:app --bind 127.0.0.1:{port}",
                                port = BACKEND_PORT,
                            );
                            e
                        })
                        .ok()
                }
            };

            match child {
                Some(c) => {
                    let pid = c.id();
                    log::info!(
                        "Backend started (PID: {pid}). API at http://127.0.0.1:{port}",
                        port = BACKEND_PORT,
                    );
                    app.manage(BackendProcess(Mutex::new(Some(c))));
                }
                None => {
                    log::warn!("Backend not available — some features will be disabled");
                    app.manage(BackendProcess(Mutex::new(None)));
                }
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                log::info!("Window close requested — killing backend...");
                let app = window.app_handle();
                if let Some(state) = app.try_state::<BackendProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(ref mut child) = *guard {
                            let pid = child.id();
                            log::info!("Shutting down backend (PID: {pid})...");
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
                kill_backend_processes();
                log::info!("Backend stopped.");
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|_app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            kill_backend_processes();
        }
    });
}