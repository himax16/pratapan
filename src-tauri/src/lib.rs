use std::sync::{Arc, Mutex};
use tauri::{Emitter, Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

fn normalize_sidecar_output(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes)
        .trim_end_matches(['\r', '\n'])
        .to_string()
}

#[tauri::command]
fn toggle_fullscreen(window: tauri::Window) {
    if let Ok(is_fullscreen) = window.is_fullscreen() {
        let _ = window.set_fullscreen(!is_fullscreen);
    }
}

fn stop_sidecar(app_handle: &tauri::AppHandle) {
    if let Some(state) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
        if let Ok(mut guard) = state.lock() {
            if let Some(mut process) = guard.take() {
                // Ask sidecar to shut down gracefully first, then force-kill
                // after a short grace period so orphans never leak on Windows
                // (which would hold an exclusive lock on the .exe file).
                let _ = process.write(b"sidecar shutdown\n");
                std::thread::sleep(std::time::Duration::from_millis(1500));
                let _ = process.kill();
            }
        }
    }
}

// Helper function to spawn the sidecar and monitor its stdout/stderr.
fn spawn_and_monitor_sidecar(app_handle: tauri::AppHandle) -> Result<(), String> {
    // Check if a sidecar process already exists.
    if let Some(state) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
        if let Ok(child_process) = state.lock() {
            if child_process.is_some() {
                // A sidecar is already running, do not spawn a new one.
                println!("[tauri] Sidecar is already running. Skipping spawn.");
                return Ok(());
            }
        }
    }

    // Use the name configured in tauri.conf.json -> bundle.externalBin.
    let sidecar_command = app_handle
        .shell()
        .sidecar("pratapan-sidecar")
        .map_err(|e| e.to_string())?;
    let (mut rx, child) = sidecar_command.spawn().map_err(|e| e.to_string())?;

    // Store the child process in app state.
    if let Some(state) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
        if let Ok(mut guard) = state.lock() {
            *guard = Some(child);
        } else {
            return Err("Failed to acquire sidecar process lock".to_string());
        }
    } else {
        return Err("Failed to access app state".to_string());
    }

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line_bytes) => {
                    let line = normalize_sidecar_output(&line_bytes);
                    println!("Sidecar stdout: {}", line);
                    let _ = app_handle.emit("sidecar-stdout", line);
                }
                CommandEvent::Stderr(line_bytes) => {
                    let line = normalize_sidecar_output(&line_bytes);
                    eprintln!("Sidecar stderr: {}", line);
                    let _ = app_handle.emit("sidecar-stderr", line);
                }
                CommandEvent::Terminated(status) => {
                    println!("[tauri] Sidecar terminated: {:?}", status);
                    if let Some(state) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
                        if let Ok(mut child_process) = state.lock() {
                            *child_process = None;
                        }
                    }
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(())
}

#[tauri::command]
fn shutdown_sidecar(app_handle: tauri::AppHandle) -> Result<String, String> {
    println!("[tauri] Received command to shutdown sidecar.");
    stop_sidecar(&app_handle);
    Ok("Sidecar shutdown attempted.".to_string())
}

#[tauri::command]
fn start_sidecar(app_handle: tauri::AppHandle) -> Result<String, String> {
    println!("[tauri] Received command to start sidecar.");
    spawn_and_monitor_sidecar(app_handle)?;
    Ok("Sidecar spawned and monitoring started.".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .manage(Arc::new(Mutex::new(None::<CommandChild>)))
        .setup(|app| {
            println!("[tauri] Creating sidecar...");
            spawn_and_monitor_sidecar(app.handle().clone()).ok();
            println!("[tauri] Sidecar spawned and monitoring started.");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start_sidecar,
            shutdown_sidecar,
            toggle_fullscreen
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| match event {
            RunEvent::ExitRequested { .. } => {
                stop_sidecar(app_handle);
                println!("[tauri] Sidecar closed.");
            }
            _ => {}
        });
}
