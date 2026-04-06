mod commands;
mod db;
mod models;
mod process;

use db::AppDb;
use process::DaemonProcess;
use std::path::PathBuf;
use tauri::menu::{MenuBuilder, MenuItemBuilder};
use tauri::tray::TrayIconBuilder;
use tauri::{Manager, RunEvent, WindowEvent};

/// Resolve data_dir, config_dir, python_bin, and daemon_src based on
/// whether we are running in dev mode or as a packaged application.
fn resolve_paths(app: &tauri::App) -> (PathBuf, PathBuf, PathBuf, PathBuf) {
    if cfg!(debug_assertions) {
        // Dev mode: CARGO_MANIFEST_DIR = web/src-tauri/
        // Repo root is two levels up: web/src-tauri/ -> web/ -> repo/
        let manifest_dir =
            PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let repo_root = manifest_dir
            .parent()
            .and_then(|p| p.parent())
            .expect("Cannot resolve repo root from CARGO_MANIFEST_DIR")
            .to_path_buf();

        let data_dir = repo_root.join("data");
        let config_dir = repo_root.clone();
        let python_bin = PathBuf::from("python3");
        let daemon_src = repo_root.join("daemon");

        (data_dir, config_dir, python_bin, daemon_src)
    } else {
        // Packaged mode
        let app_data = app
            .path()
            .app_data_dir()
            .expect("Cannot resolve app data dir");
        let resource_dir = app
            .path()
            .resource_dir()
            .expect("Cannot resolve resource dir");

        let data_dir = app_data.join("data");
        let config_dir = app_data.clone();
        let python_bin = resource_dir.join("python3");
        let daemon_src = resource_dir.join("daemon");

        (data_dir, config_dir, python_bin, daemon_src)
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            let (data_dir, config_dir, python_bin, daemon_src) = resolve_paths(app);

            // Ensure data directory exists
            std::fs::create_dir_all(&data_dir).map_err(|e| {
                format!("Failed to create data dir {}: {e}", data_dir.display())
            })?;

            // Open database
            let db = AppDb::new(data_dir.clone(), config_dir.clone())
                .map_err(|e| format!("DB init failed: {e}"))?;
            app.manage(db);

            // Start daemon process
            let daemon = DaemonProcess::new();
            if let Err(e) = daemon.start(&python_bin, &config_dir, &daemon_src, &data_dir) {
                eprintln!("Warning: failed to start daemon: {e}");
                // Non-fatal — the app can still browse existing data
            }
            app.manage(daemon);

            // ── System tray ─────────────────────────────────────────────
            let open_item = MenuItemBuilder::with_id("open", "Open homelife.ai").build(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "Quit").build(app)?;

            let menu = MenuBuilder::new(app)
                .item(&open_item)
                .separator()
                .item(&quit_item)
                .build()?;

            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("homelife.ai")
                .on_menu_event(move |app, event| match event.id().as_ref() {
                    "open" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "quit" => {
                        // Stop daemon before exiting
                        if let Some(d) = app.try_state::<DaemonProcess>() {
                            d.stop();
                        }
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            // Close-to-tray: hide the window instead of quitting
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .invoke_handler(tauri::generate_handler![
            // frames
            commands::frames::get_frames,
            commands::frames::get_frame,
            commands::frames::get_latest_frame,
            // stats
            commands::stats::get_stats,
            commands::stats::get_activities,
            commands::stats::get_apps,
            commands::stats::get_dates,
            commands::stats::get_range_stats,
            // summaries
            commands::summaries::get_summaries,
            // events
            commands::events::get_events,
            // sessions
            commands::sessions::get_sessions,
            // search
            commands::search::search_text,
            // reports
            commands::reports::get_report,
            commands::reports::list_reports,
            // memos
            commands::memos::get_memo,
            commands::memos::put_memo,
            // activities
            commands::activities::list_activities,
            commands::activities::get_activity_mappings,
            // chat
            commands::chat::get_chat,
            // settings
            commands::settings::get_settings,
            commands::settings::put_settings,
            // context
            commands::context::get_context,
            commands::context::put_context,
            // status
            commands::status::get_status,
            // devices
            commands::devices::get_devices,
            // data
            commands::data::get_data_stats,
            commands::data::export_table,
            // export
            commands::export::export_frames_csv,
            commands::export::export_summaries_csv,
            commands::export::export_report,
            // rag
            commands::rag::ask_rag,
            // live
            commands::live::get_live_frame,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                // Clean up daemon on app exit
                if let Some(daemon) = app.try_state::<DaemonProcess>() {
                    daemon.stop();
                }
            }
        });
}
