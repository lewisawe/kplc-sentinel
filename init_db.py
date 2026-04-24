import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "kplc.sqlite")

def get_db():
    """Return a connection usable as a context manager."""
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                token TEXT UNIQUE,
                units REAL,
                amount REAL,
                raw_text TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                balance REAL,
                notes TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profile (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

if __name__ == "__main__":
    init_db()
