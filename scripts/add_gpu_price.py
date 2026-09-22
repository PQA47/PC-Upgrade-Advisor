import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "pc_advisor.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check whether the price column already exists
cursor.execute("PRAGMA table_info(gpus)")
columns = [column[1] for column in cursor.fetchall()]

if "price" not in columns:
    cursor.execute(
        "ALTER TABLE gpus ADD COLUMN price REAL DEFAULT 0.0"
    )
    print("✓ Added price column to gpus table")
else:
    print("✓ price column already exists")

conn.commit()
conn.close()