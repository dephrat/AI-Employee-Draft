import sqlite3

DB_PATH = "ai_employee.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gmail_id TEXT UNIQUE,
            sender TEXT,
            subject TEXT,
            body TEXT,
            draft_reply TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_setting(key, default=None, account=None):
    full_key = f"{account}:{key}" if account else key
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (full_key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def save_setting(key, value, account=None):
    full_key = f"{account}:{key}" if account else key
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (full_key, value))
    conn.commit()
    conn.close()
    