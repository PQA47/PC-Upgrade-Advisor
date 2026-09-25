from pathlib import Path
import sqlite3

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "pc_advisor.db"

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_schema_columns() -> None:
    """Apply small SQLite migrations required by the current SQLAlchemy models.

    create_all() does not add new columns to an existing table. This migration is
    intentionally tiny and idempotent so an existing user's database is preserved.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        migrations = {
            "cpus": [("price", "FLOAT DEFAULT 0.0")],
            "gpus": [("price", "FLOAT DEFAULT 0.0")],
            "analyses": [("result_json", "TEXT")],
        }

        for table, additions in migrations.items():
            columns = {
                row[1]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if not columns:
                # Table may not exist yet; Base.metadata.create_all() will create it.
                continue
            for column_name, column_def in additions:
                if column_name not in columns:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column_name} {column_def}"
                    )
                    print(f"✓ Database migration: added {table}.{column_name}")
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
