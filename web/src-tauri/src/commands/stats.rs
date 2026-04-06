use crate::db::AppDb;
use crate::models::{ActivityStat, ActivityStats, AppStat, DayStats, HourlyActivityStat, RangeDay, RangeStats};
use std::collections::HashMap;
use tauri::State;

#[tauri::command]
pub fn get_stats(date: String, db: State<AppDb>) -> Result<DayStats, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let start = format!("{date}T00:00:00");
    let end = format!("{date}T23:59:59");

    let frames: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM frames WHERE timestamp BETWEEN ?1 AND ?2",
            rusqlite::params![start, end],
            |row| row.get(0),
        )
        .unwrap_or(0);

    let events: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM events WHERE timestamp BETWEEN ?1 AND ?2",
            rusqlite::params![start, end],
            |row| row.get(0),
        )
        .unwrap_or(0);

    let summaries: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM summaries WHERE timestamp BETWEEN ?1 AND ?2",
            rusqlite::params![start, end],
            |row| row.get(0),
        )
        .unwrap_or(0);

    let avg_motion: f64 = conn
        .query_row(
            "SELECT AVG(motion_score) FROM frames WHERE timestamp BETWEEN ?1 AND ?2",
            rusqlite::params![start, end],
            |row| row.get::<_, Option<f64>>(0),
        )
        .unwrap_or(None)
        .unwrap_or(0.0);

    let avg_brightness: f64 = conn
        .query_row(
            "SELECT AVG(brightness) FROM frames WHERE timestamp BETWEEN ?1 AND ?2",
            rusqlite::params![start, end],
            |row| row.get::<_, Option<f64>>(0),
        )
        .unwrap_or(None)
        .unwrap_or(0.0);

    // Hourly activity (frames per hour)
    let mut stmt = conn
        .prepare(
            "SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) as count
             FROM frames WHERE timestamp BETWEEN ?1 AND ?2
             GROUP BY hour ORDER BY hour",
        )
        .map_err(|e| e.to_string())?;

    let hourly_rows = stmt
        .query_map(rusqlite::params![start, end], |row| {
            Ok((row.get::<_, i64>(0)?, row.get::<_, i64>(1)?))
        })
        .map_err(|e| e.to_string())?;

    let mut hourly_map: HashMap<i64, i64> = HashMap::new();
    for row in hourly_rows.flatten() {
        hourly_map.insert(row.0, row.1);
    }

    let activity: Vec<i64> = (0..24)
        .map(|h| *hourly_map.get(&h).unwrap_or(&0))
        .collect();

    Ok(DayStats {
        date,
        frames,
        events,
        summaries,
        avg_motion: avg_motion,
        avg_brightness: avg_brightness,
        activity,
    })
}

fn estimate_frame_duration(conn: &rusqlite::Connection, start: &str, end: &str) -> i64 {
    let result: Option<f64> = conn
        .query_row(
            "SELECT MIN(julianday(t2.timestamp) - julianday(t1.timestamp)) * 86400
             FROM frames t1, frames t2
             WHERE t1.timestamp BETWEEN ?1 AND ?2 AND t2.timestamp BETWEEN ?1 AND ?2
               AND t2.rowid = t1.rowid + 1",
            rusqlite::params![start, end],
            |row| row.get(0),
        )
        .unwrap_or(None);

    match result {
        Some(sec) if sec > 0.0 => sec.round() as i64,
        _ => 30,
    }
}

#[tauri::command]
pub fn get_activities(date: String, db: State<AppDb>) -> Result<ActivityStats, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let start = format!("{date}T00:00:00");
    let end = format!("{date}T23:59:59");

    let frame_duration = estimate_frame_duration(&conn, &start, &end);

    // Activity totals
    let mut stmt = conn
        .prepare(
            "SELECT activity, COUNT(*) as frame_count
             FROM frames WHERE timestamp BETWEEN ?1 AND ?2 AND activity != ''
             GROUP BY activity ORDER BY frame_count DESC",
        )
        .map_err(|e| e.to_string())?;

    let activities: Vec<ActivityStat> = stmt
        .query_map(rusqlite::params![start, end], |row| {
            let frame_count: i64 = row.get(1)?;
            Ok(ActivityStat {
                activity: row.get(0)?,
                frame_count,
                duration_sec: frame_count * frame_duration,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    // Hourly breakdown
    let mut stmt = conn
        .prepare(
            "SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                    activity, COUNT(*) as frame_count
             FROM frames WHERE timestamp BETWEEN ?1 AND ?2 AND activity != ''
             GROUP BY hour, activity ORDER BY hour, frame_count DESC",
        )
        .map_err(|e| e.to_string())?;

    let hourly: Vec<HourlyActivityStat> = stmt
        .query_map(rusqlite::params![start, end], |row| {
            let frame_count: i64 = row.get(2)?;
            Ok(HourlyActivityStat {
                hour: row.get(0)?,
                activity: row.get(1)?,
                frame_count,
                duration_sec: frame_count * frame_duration,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    Ok(ActivityStats { activities, hourly })
}

#[tauri::command]
pub fn get_apps(date: String, db: State<AppDb>) -> Result<Vec<AppStat>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let start = format!("{date}T00:00:00");
    let end = format!("{date}T23:59:59");

    // Check if window_events table exists
    let table_exists: bool = conn
        .query_row(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='window_events'",
            [],
            |row| row.get::<_, i64>(0),
        )
        .unwrap_or(0)
        > 0;

    if !table_exists {
        return Ok(vec![]);
    }

    // Get events with next timestamp via window function
    let mut stmt = conn
        .prepare(
            "SELECT timestamp, process_name, window_title,
                    LEAD(timestamp, 1, ?1) OVER (ORDER BY timestamp) as next_ts
             FROM window_events
             WHERE timestamp BETWEEN ?2 AND ?1
             ORDER BY timestamp",
        )
        .map_err(|e| e.to_string())?;

    struct WindowRow {
        timestamp: String,
        process_name: String,
        window_title: String,
        next_ts: String,
    }

    let rows: Vec<WindowRow> = stmt
        .query_map(rusqlite::params![end, start], |row| {
            Ok(WindowRow {
                timestamp: row.get::<_, Option<String>>(0)?.unwrap_or_default(),
                process_name: row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                window_title: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
                next_ts: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    // Aggregate by process name
    struct ProcessAgg {
        duration_sec: f64,
        title_sample: String,
        max_duration: f64,
        switch_count: i64,
    }

    let mut by_process: HashMap<String, ProcessAgg> = HashMap::new();

    for row in &rows {
        if row.process_name.is_empty() {
            continue;
        }

        // Parse timestamps to compute duration
        let duration = parse_duration_secs(&row.timestamp, &row.next_ts);
        if duration <= 0.0 || duration > 86400.0 {
            continue;
        }

        let entry = by_process
            .entry(row.process_name.clone())
            .or_insert(ProcessAgg {
                duration_sec: 0.0,
                title_sample: row.window_title.clone(),
                max_duration: 0.0,
                switch_count: 0,
            });

        entry.duration_sec += duration;
        entry.switch_count += 1;
        if duration > entry.max_duration {
            entry.title_sample = row.window_title.clone();
            entry.max_duration = duration;
        }
    }

    let mut apps: Vec<AppStat> = by_process
        .into_iter()
        .map(|(process, data)| AppStat {
            process,
            title_sample: data.title_sample,
            duration_sec: data.duration_sec.round() as i64,
            switch_count: data.switch_count,
        })
        .collect();

    apps.sort_by(|a, b| b.duration_sec.cmp(&a.duration_sec));

    Ok(apps)
}

/// Parse two ISO timestamp strings and return the difference in seconds.
fn parse_duration_secs(ts1: &str, ts2: &str) -> f64 {
    // Simple ISO 8601 parsing: YYYY-MM-DDTHH:MM:SS
    use chrono::NaiveDateTime;
    let fmt = "%Y-%m-%dT%H:%M:%S";
    let t1 = NaiveDateTime::parse_from_str(ts1, fmt)
        .or_else(|_| NaiveDateTime::parse_from_str(&ts1[..19.min(ts1.len())], fmt));
    let t2 = NaiveDateTime::parse_from_str(ts2, fmt)
        .or_else(|_| NaiveDateTime::parse_from_str(&ts2[..19.min(ts2.len())], fmt));
    match (t1, t2) {
        (Ok(a), Ok(b)) => (b - a).num_milliseconds() as f64 / 1000.0,
        _ => 0.0,
    }
}

#[tauri::command]
pub fn get_dates(db: State<AppDb>) -> Result<Vec<String>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare("SELECT DISTINCT date(timestamp) as d FROM frames ORDER BY d DESC")
        .map_err(|e| e.to_string())?;

    let rows = stmt
        .query_map([], |row| row.get::<_, String>(0))
        .map_err(|e| e.to_string())?;

    let mut dates = Vec::new();
    for row in rows.flatten() {
        dates.push(row);
    }
    Ok(dates)
}

#[tauri::command]
pub fn get_range_stats(
    from: String,
    to: String,
    db: State<AppDb>,
) -> Result<RangeStats, String> {
    let start = format!("{from}T00:00:00");
    let end = format!("{to}T23:59:59");

    struct DailyActivity {
        date: String,
        activity: String,
        frame_count: i64,
    }

    let (frame_duration, daily_frames, daily_activities) = {
        let conn = db.conn.lock().map_err(|e| e.to_string())?;

        let fd = estimate_frame_duration(&conn, &start, &end);

        // Per-day frame counts
        let mut stmt = conn
            .prepare(
                "SELECT date(timestamp) as d, COUNT(*) as frame_count
                 FROM frames WHERE timestamp BETWEEN ?1 AND ?2
                 GROUP BY d ORDER BY d",
            )
            .map_err(|e| e.to_string())?;

        let df: Vec<(String, i64)> = stmt
            .query_map(rusqlite::params![start, end], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?))
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();

        // Per-day activity breakdown
        let mut stmt2 = conn
            .prepare(
                "SELECT date(timestamp) as d, activity, COUNT(*) as frame_count
                 FROM frames WHERE timestamp BETWEEN ?1 AND ?2 AND activity != ''
                 GROUP BY d, activity ORDER BY d, frame_count DESC",
            )
            .map_err(|e| e.to_string())?;

        let da: Vec<DailyActivity> = stmt2
            .query_map(rusqlite::params![start, end], |row| {
                Ok(DailyActivity {
                    date: row.get(0)?,
                    activity: row.get(1)?,
                    frame_count: row.get(2)?,
                })
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();

        (fd, df, da)
    };
    // conn lock is released here

    let mappings = db.get_activity_mappings();

    // Build per-day meta-category map
    let mut meta_by_day: HashMap<String, HashMap<String, i64>> = HashMap::new();
    for da in &daily_activities {
        let meta = mappings.get(&da.activity).cloned().unwrap_or_else(|| "other".to_string());
        let day_entry = meta_by_day.entry(da.date.clone()).or_default();
        *day_entry.entry(meta).or_insert(0) += da.frame_count;
    }

    let mut days = Vec::new();
    let mut total_frames: i64 = 0;
    let mut activity_totals: HashMap<String, i64> = HashMap::new();
    let mut meta_totals: HashMap<String, i64> = HashMap::new();

    for (d, frame_count) in &daily_frames {
        total_frames += frame_count;

        let mut activities: HashMap<String, i64> = HashMap::new();
        for da in daily_activities.iter().filter(|a| &a.date == d) {
            let sec = da.frame_count * frame_duration;
            activities.insert(da.activity.clone(), sec);
            *activity_totals.entry(da.activity.clone()).or_insert(0) += sec;
        }

        let meta_categories = meta_by_day.get(d).cloned().unwrap_or_default();
        for (meta, count) in &meta_categories {
            *meta_totals.entry(meta.clone()).or_insert(0) += count;
        }

        days.push(RangeDay {
            date: d.clone(),
            frame_count: *frame_count,
            total_sec: frame_count * frame_duration,
            activities,
            meta_categories,
        });
    }

    Ok(RangeStats {
        from,
        to,
        frame_duration,
        total_frames,
        total_sec: total_frames * frame_duration,
        days,
        activity_totals,
        meta_totals,
    })
}
