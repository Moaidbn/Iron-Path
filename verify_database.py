"""فحص محلي قصير لسلامة قاعدة بيانات الحملة قبل التسليم."""
from pathlib import Path
import sqlite3

path = Path("data/story.db")
with sqlite3.connect(path) as connection:
    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    scenes = connection.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]

if result != "ok":
    raise SystemExit(f"Database integrity check failed: {result}")
print(f"DATABASE_OK scenes={scenes}")
