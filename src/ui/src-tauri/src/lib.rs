#[cfg_attr(mobile, tauri::mobile_entry_point)]
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, WindowEvent,
};
use tauri_plugin_shell::ShellExt;

#[tauri::command]
async fn get_runtime_port(app_handle: tauri::AppHandle) -> u16 {
    let mut port = 8000;
    let app_home = if let Ok(val) = std::env::var("FRIDAY_HOME") {
        if !val.trim().is_empty() {
            Some(std::path::PathBuf::from(val))
        } else {
            app_handle.path().home_dir().ok().map(|h| h.join(".friday"))
        }
    } else {
        app_handle.path().home_dir().ok().map(|h| h.join(".friday"))
    };

    if let Some(home) = app_home {
        let port_file = home.join("runtime_port");
        for _ in 0..60 {
            if let Ok(contents) = std::fs::read_to_string(&port_file) {
                if let Ok(p) = contents.trim().parse::<u16>() {
                    return p;
                }
            }
            tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        }
    }
    port
}

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_runtime_port])
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Create tray menu
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let show_i = MenuItem::with_id(app, "show", "Show Friday", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &quit_i])?;

            // Spawn the Python sidecar
            let sidecar = app
                .shell()
                .sidecar("friday-api")
                .expect("Failed to create sidecar command");
            let (mut rx, child) = sidecar.spawn().expect("Failed to spawn sidecar");
            
            let child_arc = std::sync::Arc::new(std::sync::Mutex::new(Some(child)));
            let child_for_menu = child_arc.clone();

            tauri::async_runtime::spawn(async move {
                // Read stdout/stderr so the buffer doesn't fill up
                while let Some(_) = rx.recv().await {
                    // Just consume
                }
            });

            // Setup tray icon
            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .icon(app.default_window_icon().unwrap().clone())
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "quit" => {
                        if let Some(child) = child_for_menu.lock().unwrap().take() {
                            let _ = child.kill();
                        }
                        app.exit(0);
                    }
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let tauri::tray::TrayIconEvent::Click {
                        button: tauri::tray::MouseButton::Left,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| match event {
            WindowEvent::CloseRequested { api, .. } => {
                // Prevent window from closing, hide it instead
                api.prevent_close();
                let _ = window.hide();
            }
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
