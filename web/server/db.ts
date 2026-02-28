import Database from 'better-sqlite3';
import { resolve } from 'node:path';

export const DATA_DIR = process.env.DATA_DIR || resolve(process.cwd(), '../data');
export const DB_PATH = resolve(DATA_DIR, 'life.db');

let _db: Database.Database | null = null;
let _writeDb: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH, { readonly: true });
    _db.pragma('journal_mode = WAL');
  }
  return _db;
}

export function getWriteDb(): Database.Database {
  if (!_writeDb) {
    _writeDb = new Database(DB_PATH);
    _writeDb.pragma('journal_mode = WAL');
    _writeDb.exec(`
      CREATE TABLE IF NOT EXISTS memos (
        date TEXT PRIMARY KEY,
        content TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      )
    `);
  }
  return _writeDb;
}
