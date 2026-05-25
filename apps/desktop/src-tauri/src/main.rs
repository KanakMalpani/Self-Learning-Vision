use serde::Serialize;
use serde_json::Value;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Manager, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const MAX_START_ATTEMPTS: u8 = 3;
const READINESS_TIMEOUT: Duration = Duration::from_secs(10);

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

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct EngineStatus {
    status: String,
    message: String,
    detail: Option<String>,
    attempt: u8,
    max_attempts: u8,
}

struct DesktopState {
    config: Mutex<RuntimeConfig>,
    engine: Mutex<EngineStatus>,
    sidecar: Mutex<Option<(u64, CommandChild)>>,
    generation: Mutex<u64>,
    app_data_dir: String,
}

fn free_local_port() -> Result<u16, String> {
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|err| err.to_string())?;
    let port = listener.local_addr().map_err(|err| err.to_string())?.port();
    drop(listener);
    Ok(port)
}

fn engine_status(
    status: &str,
    message: impl Into<String>,
    detail: Option<String>,
    attempt: u8,
) -> EngineStatus {
    EngineStatus {
        status: status.to_string(),
        message: message.into(),
        detail,
        attempt,
        max_attempts: MAX_START_ATTEMPTS,
    }
}

fn active_generation(app: &AppHandle, generation: u64) -> bool {
    app.state::<DesktopState>()
        .generation
        .lock()
        .map(|current| *current == generation)
        .unwrap_or(false)
}

fn set_status(app: &AppHandle, generation: u64, status: EngineStatus) {
    if !active_generation(app, generation) {
        return;
    }
    if let Ok(mut current) = app.state::<DesktopState>().engine.lock() {
        *current = status;
    }
}

fn set_api_base_url(app: &AppHandle, generation: u64, url: String) {
    if !active_generation(app, generation) {
        return;
    }
    if let Ok(mut config) = app.state::<DesktopState>().config.lock() {
        config.api_base_url = url;
    }
}

fn kill_generation_sidecar(app: &AppHandle, generation: u64) {
    if let Ok(mut sidecar) = app.state::<DesktopState>().sidecar.lock() {
        if sidecar.as_ref().map(|(id, _)| *id) == Some(generation) {
            if let Some((_, child)) = sidecar.take() {
                let _ = child.kill();
            }
        }
    }
}

fn kill_all_sidecars(app: &AppHandle) {
    if let Ok(mut sidecar) = app.state::<DesktopState>().sidecar.lock() {
        if let Some((_, child)) = sidecar.take() {
            let _ = child.kill();
        }
    }
}

fn readiness_ok(port: u16) -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(500)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(750)));
    let request = b"GET /ready HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    if stream.write_all(request).is_err() {
        return false;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() || !response.starts_with("HTTP/1.1 200") {
        return false;
    }
    let Some(body) = response.split("\r\n\r\n").nth(1) else {
        return false;
    };
    serde_json::from_str::<Value>(body)
        .ok()
        .and_then(|payload| {
            payload
                .get("status")
                .and_then(Value::as_str)
                .map(String::from)
        })
        .map(|status| status == "ok")
        .unwrap_or(false)
}

fn begin_engine_start(app: AppHandle) -> EngineStatus {
    let generation = {
        let state = app.state::<DesktopState>();
        let mut current = state
            .generation
            .lock()
            .expect("desktop generation lock poisoned");
        *current += 1;
        *current
    };
    kill_all_sidecars(&app);
    let initial = engine_status("starting", "Starting local engine...", None, 1);
    set_status(&app, generation, initial.clone());

    thread::spawn(move || {
        let mut failures = Vec::new();
        for attempt in 1..=MAX_START_ATTEMPTS {
            if !active_generation(&app, generation) {
                return;
            }

            let port = match free_local_port() {
                Ok(port) => port,
                Err(error) => {
                    failures.push(format!(
                        "Attempt {attempt}: could not select a loopback port ({error})."
                    ));
                    continue;
                }
            };
            let api_base_url = format!("http://127.0.0.1:{port}");
            set_api_base_url(&app, generation, api_base_url);
            set_status(
                &app,
                generation,
                engine_status(
                    "starting",
                    format!("Starting local engine (attempt {attempt} of {MAX_START_ATTEMPTS})..."),
                    None,
                    attempt,
                ),
            );

            let app_data_dir = app.state::<DesktopState>().app_data_dir.clone();
            let spawned = app
                .shell()
                .sidecar("slv-api-sidecar")
                .map_err(|error| format!("could not load bundled API ({error})"))
                .and_then(|command| {
                    command
                        .args([
                            "--host",
                            "127.0.0.1",
                            "--port",
                            &port.to_string(),
                            "--app-data-dir",
                            &app_data_dir,
                        ])
                        .spawn()
                        .map_err(|error| format!("could not start bundled API ({error})"))
                });
            let (mut events, child) = match spawned {
                Ok(process) => process,
                Err(error) => {
                    failures.push(format!("Attempt {attempt}: {error}."));
                    continue;
                }
            };

            if !active_generation(&app, generation) {
                let _ = child.kill();
                return;
            }
            if let Ok(mut current) = app.state::<DesktopState>().sidecar.lock() {
                *current = Some((generation, child));
            }

            let started_at = Instant::now();
            while active_generation(&app, generation) && started_at.elapsed() < READINESS_TIMEOUT {
                if readiness_ok(port) {
                    set_status(
                        &app,
                        generation,
                        engine_status("ready", "Local engine ready.", None, attempt),
                    );
                    let monitor_app = app.clone();
                    tauri::async_runtime::spawn(async move {
                        while let Some(event) = events.recv().await {
                            if let CommandEvent::Terminated(payload) = event {
                                if active_generation(&monitor_app, generation) {
                                    kill_generation_sidecar(&monitor_app, generation);
                                    set_status(
                                        &monitor_app,
                                        generation,
                                        engine_status(
                                            "failed",
                                            "Local engine stopped unexpectedly.",
                                            Some(format!(
                                                "The bundled local API exited (code {:?}).",
                                                payload.code
                                            )),
                                            attempt,
                                        ),
                                    );
                                }
                                break;
                            }
                        }
                    });
                    return;
                }
                thread::sleep(Duration::from_millis(250));
            }
            kill_generation_sidecar(&app, generation);
            failures.push(format!(
                "Attempt {attempt}: local engine did not become ready in time."
            ));
        }

        set_status(
            &app,
            generation,
            engine_status(
                "failed",
                "Local engine failed to start.",
                Some(failures.join(" ")),
                MAX_START_ATTEMPTS,
            ),
        );
    });

    initial
}

fn stop_engine(app: &AppHandle) {
    if let Ok(mut generation) = app.state::<DesktopState>().generation.lock() {
        *generation += 1;
    }
    kill_all_sidecars(app);
    if let Ok(mut engine) = app.state::<DesktopState>().engine.lock() {
        *engine = engine_status("stopped", "Local engine stopped.", None, 0);
    }
}

#[tauri::command]
fn get_runtime_config(state: State<'_, DesktopState>) -> RuntimeConfig {
    state
        .config
        .lock()
        .expect("desktop config lock poisoned")
        .clone()
}

#[tauri::command]
fn get_engine_status(state: State<'_, DesktopState>) -> EngineStatus {
    state
        .engine
        .lock()
        .expect("desktop engine lock poisoned")
        .clone()
}

#[tauri::command]
fn restart_local_engine(app: AppHandle) -> EngineStatus {
    begin_engine_start(app)
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let app_data_dir = app
                .path()
                .app_data_dir()
                .map_err(|err| format!("Could not resolve app data directory: {err}"))?;
            std::fs::create_dir_all(&app_data_dir)
                .map_err(|err| format!("Could not create app data directory: {err}"))?;
            let app_data_string = app_data_dir.to_string_lossy().to_string();

            app.manage(DesktopState {
                config: Mutex::new(RuntimeConfig {
                    api_base_url: "http://127.0.0.1:0".to_string(),
                    app_version: app.package_info().version.to_string(),
                    app_data_dir: app_data_string.clone(),
                    database_mode: "sqlite".to_string(),
                    provider_mode: "local".to_string(),
                    desktop_mode: true,
                }),
                engine: Mutex::new(engine_status(
                    "starting",
                    "Starting local engine...",
                    None,
                    1,
                )),
                sidecar: Mutex::new(None),
                generation: Mutex::new(0),
                app_data_dir: app_data_string,
            });
            begin_engine_start(app.handle().clone());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_runtime_config,
            get_engine_status,
            restart_local_engine
        ])
        .build(tauri::generate_context!())
        .expect("error while building Self-Learning Vision desktop app");

    app.run(|app_handle, event| {
        if matches!(
            event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        ) {
            stop_engine(app_handle);
        }
    });
}
