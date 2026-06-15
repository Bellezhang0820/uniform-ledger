import os
import sqlite3
from pathlib import Path
from flask import current_app, g
from ledger.parser import PRICE_SEED

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  store_id INTEGER DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  source TEXT NOT NULL,
  raw_text TEXT,
  status TEXT NOT NULL DEFAULT 'confirmed',
  final_override INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  school_level TEXT NOT NULL,
  fabric_type TEXT NOT NULL,
  item_type TEXT NOT NULL,
  size TEXT,
  qty INTEGER NOT NULL,
  unit_price REAL NOT NULL,
  cost_price REAL NOT NULL DEFAULT 0,
  unit TEXT NOT NULL,
  note TEXT,
  return_flag INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS price_list (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  school_level TEXT NOT NULL,
  fabric_type TEXT NOT NULL,
  item_type TEXT NOT NULL,
  sell_price REAL NOT NULL,
  cost_price REAL NOT NULL,
  unit TEXT NOT NULL,
  UNIQUE(school_level, fabric_type, item_type)
);
CREATE TABLE IF NOT EXISTS reconciliation_sets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  date TEXT NOT NULL,
  our_items_json TEXT NOT NULL,
  their_items_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


def db_path(app=None):
    if app:
        return app.config.get("DATABASE")
    return os.environ.get("LEDGER_DB", str(Path("data") / "ledger.db"))


def get_db():
    if "db" not in g:
        path = current_app.config["DATABASE"]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    path = app.config["DATABASE"]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        for school, fabric, item, sell, unit in PRICE_SEED:
            conn.execute(
                """
                INSERT OR IGNORE INTO price_list
                (school_level, fabric_type, item_type, sell_price, cost_price, unit)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (school, fabric, item, sell, round(sell * 0.7, 2), unit),
            )
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}
