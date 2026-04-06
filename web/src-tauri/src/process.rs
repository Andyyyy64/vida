use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

/// Manages the Python daemon process lifecycle.
///
/// The daemon is spawned as a child process and can be started/stopped
/// from Tauri.  The `Drop` implementation ensures cleanup on exit.
pub struct DaemonProcess {
    child: Mutex<Option<Child>>,
}

impl DaemonProcess {
    pub fn new() -> Self {
        Self {
            child: Mutex::new(None),
        }
    }

    /// Spawn the Python daemon process.
    ///
    /// - `python_bin` — path to the Python interpreter (e.g. `python3`)
    /// - `config_dir` — directory containing `life.toml` and `.env`
    /// - `daemon_src` — path to the daemon Python package directory
    /// - `data_dir`   — path to the data/ directory for frames, DB, etc.
    pub fn start(
        &self,
        python_bin: &PathBuf,
        config_dir: &PathBuf,
        daemon_src: &PathBuf,
        data_dir: &PathBuf,
    ) -> Result<(), String> {
        let mut guard = self.child.lock().unwrap();

        // Don't start if already running
        if let Some(ref mut c) = *guard {
            match c.try_wait() {
                Ok(Some(_)) => { /* exited — allow restart */ }
                Ok(None) => return Ok(()), // still running
                Err(_) => { /* error checking — allow restart */ }
            }
        }

        let child = Command::new(python_bin)
            .arg("-m")
            .arg("daemon")
            .arg("run")
            .arg("--data-dir")
            .arg(data_dir)
            .current_dir(daemon_src.parent().unwrap_or(daemon_src))
            .env("HOMELIFE_CONFIG_DIR", config_dir)
            .spawn()
            .map_err(|e| format!("Failed to start daemon: {e}"))?;

        *guard = Some(child);
        Ok(())
    }

    /// Stop the daemon process if it is running.
    pub fn stop(&self) {
        let mut guard = self.child.lock().unwrap();
        if let Some(ref mut child) = *guard {
            let _ = child.kill();
            let _ = child.wait();
        }
        *guard = None;
    }

    /// Check whether the daemon process is still running.
    pub fn is_running(&self) -> bool {
        let mut guard = self.child.lock().unwrap();
        if let Some(ref mut child) = *guard {
            match child.try_wait() {
                Ok(Some(_)) => {
                    // Process has exited
                    *guard = None;
                    false
                }
                Ok(None) => true,
                Err(_) => false,
            }
        } else {
            false
        }
    }
}

impl Drop for DaemonProcess {
    fn drop(&mut self) {
        self.stop();
    }
}
