use serde::Serialize;
use std::net::TcpListener;
use std::sync::Mutex;
use tauri::{Manager, State};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeConfig {
    api_base_url: String,
    app_version: String,
    app_data_dir: String,
    database_mode: String,
    provider_mode: String,
    desktop_mode: bool,
}

struct DesktopState {
    config: RuntimeConfig,
    sidecar: Mutex<Option<CommandChild>>,
}

fn free_local_port() -> Result<u16, String> {
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|err| err.to_string())?;
    let port = listener.local_addr().map_err(|err| err.to_string())?.port();
    drop(listener);
    Ok(port)
}

#[tauri::command]
fn get_runtime_config(state: State<DesktopState>) -> RuntimeConfig {
    state.config.clone()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let port = free_local_port().map_err(|err| format!("Could not reserve local API port: {err}"))?;
            let app_data_dir = app
                .path()
                .app_data_dir()
                .map_err(|err| format!("Could not resolve app data directory: {err}"))?;
            std::fs::create_dir_all(&app_data_dir)
                .map_err(|err| format!("Could not create app data directory: {err}"))?;

            let api_base_url = format!("http://127.0.0.1:{port}");
            let app_data_string = app_data_dir.to_string_lossy().to_string();
            let sidecar = app
                .shell()
                .sidecar("slv-api-sidecar")
                .map_err(|err| format!("Could not load API sidecar: {err}"))?
                .args([
                    "--host",
                    "127.0.0.1",
                    "--port",
                    &port.to_string(),
                    "--app-data-dir",
                    &app_data_string,
                ])
                .spawn()
                .map_err(|err| format!("Could not start API sidecar: {err}"))?
                .1;

            app.manage(DesktopState {
                config: RuntimeConfig {
                    api_base_url,
                    app_version: app.package_info().version.to_string(),
                    app_data_dir: app_data_string,
                    database_mode: "sqlite".to_string(),
                    provider_mode: "local".to_string(),
                    desktop_mode: true,
                },
                sidecar: Mutex::new(Some(sidecar)),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_runtime_config])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let app = window.app_handle();
                if let Some(state) = app.try_state::<DesktopState>() {
                    if let Ok(mut child) = state.sidecar.lock() {
                        if let Some(child) = child.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Self-Learning Vision desktop app");
}
