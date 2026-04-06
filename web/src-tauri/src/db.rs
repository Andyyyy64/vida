use rusqlite::Connection;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::Instant;

/// Application database handle wrapping a SQLite connection.
///
/// The connection is opened in WAL mode for concurrent reads from the daemon.
/// Activity mappings are cached with a 60-second TTL to avoid repeated queries.
pub struct AppDb {
    pub conn: Mutex<Connection>,
    pub data_dir: PathBuf,
    pub config_dir: PathBuf,
    mappings_cache: Mutex<Option<(HashMap<String, String>, Instant)>>,
}

const CACHE_TTL_SECS: u64 = 60;

impl AppDb {
    /// Open (or create) the SQLite database in WAL mode.
    ///
    /// Also ensures the `memos` table exists so that memo commands work even
    /// when the daemon has never run.
    pub fn new(data_dir: PathBuf, config_dir: PathBuf) -> Result<Self, String> {
        let db_path = data_dir.join("life.db");
        let conn = Connection::open(&db_path).map_err(|e| format!("Failed to open DB: {e}"))?;

        // Enable WAL mode for concurrency with the daemon writer
        conn.execute_batch("PRAGMA journal_mode=WAL;")
            .map_err(|e| format!("Failed to set WAL mode: {e}"))?;

        // Ensure memos table exists (daemon may not have created it yet)
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS memos (
                date TEXT PRIMARY KEY,
                content TEXT DEFAULT '',
                updated_at TEXT
            );",
        )
        .map_err(|e| format!("Failed to create memos table: {e}"))?;

        Ok(Self {
            conn: Mutex::new(conn),
            data_dir,
            config_dir,
            mappings_cache: Mutex::new(None),
        })
    }

    /// Return the meta-category for a given activity string.
    ///
    /// Looks up the cached activity_mappings table; returns `"other"` when
    /// the activity is empty or not found.
    pub fn get_meta_category(&self, activity: &str) -> String {
        if activity.is_empty() {
            return "other".to_string();
        }
        let mappings = self.get_activity_mappings();
        mappings
            .get(activity)
            .cloned()
            .unwrap_or_else(|| "other".to_string())
    }

    /// Return all activity -> meta_category mappings, cached for 60 seconds.
    pub fn get_activity_mappings(&self) -> HashMap<String, String> {
        // Check cache first
        {
            let cache = self.mappings_cache.lock().unwrap();
            if let Some((ref map, ref ts)) = *cache {
                if ts.elapsed().as_secs() < CACHE_TTL_SECS {
                    return map.clone();
                }
            }
        }

        // Cache miss or expired — query DB
        let map = self.query_activity_mappings();

        // Update cache
        {
            let mut cache = self.mappings_cache.lock().unwrap();
            *cache = Some((map.clone(), Instant::now()));
        }

        map
    }

    fn query_activity_mappings(&self) -> HashMap<String, String> {
        let conn = self.conn.lock().unwrap();
        let mut map = HashMap::new();

        // The table may not exist if the daemon hasn't run yet
        let mut stmt = match conn.prepare("SELECT activity, meta_category FROM activity_mappings") {
            Ok(s) => s,
            Err(_) => return map,
        };

        let rows = match stmt.query_map([], |row| {
            let activity: String = row.get(0)?;
            let meta: String = row.get(1)?;
            Ok((activity, meta))
        }) {
            Ok(r) => r,
            Err(_) => return map,
        };

        for row in rows.flatten() {
            map.insert(row.0, row.1);
        }

        map
    }
}
