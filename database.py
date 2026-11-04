import sqlite3

DB_PATH = "data.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT DEFAULT (date('now'))
        );

        CREATE TABLE IF NOT EXISTS item_transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_transaksi INTEGER NOT NULL,
            nama_item TEXT NOT NULL,
            FOREIGN KEY (id_transaksi) REFERENCES transaksi(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_item_transaksi ON item_transaksi(id_transaksi);
        CREATE INDEX IF NOT EXISTS idx_item_nama ON item_transaksi(nama_item);
        """
    )
    conn.commit()
    conn.close()

