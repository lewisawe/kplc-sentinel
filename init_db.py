import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "kplc.sqlite")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table for token purchases
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            token TEXT,
            units REAL,
            amount REAL,
            raw_text TEXT
        )
    ''')

    # Table for manual meter readings (spot checks)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            balance REAL,
            notes TEXT
        )
    ''')

    # Table for household profile and metadata
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profile (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
