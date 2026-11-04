import sqlite3
from pathlib import Path
import os

db_path = Path("data/cutflow.sqlite3")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== SQLite Schema ===")
schema = cur.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
print(schema)

print("\n=== Jobs Status Breakdown ===")
for row in cur.execute("SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"):
    print(f"Status '{row['status']}': {row['cnt']}")

print("\n=== All 26 Job IDs and details ===")
for row in cur.execute("SELECT id, status, datetime(created_at, 'unixepoch') as created, datetime(updated_at, 'unixepoch') as updated FROM jobs ORDER BY created_at DESC"):
    print(f"{row['id']} | {row['status']} | created: {row['created']} | updated: {row['updated']}")

conn.close()

print("\n=== data/uploads inspection ===")
uploads_dir = Path("data/uploads")
if uploads_dir.exists():
    upload_items = list(uploads_dir.iterdir())
    print(f"Uploads count: {len(upload_items)}")
    total_size = sum(f.stat().st_size for f in uploads_dir.glob("**/*") if f.is_file())
    print(f"Total uploads size: {total_size / (1024*1024):.2f} MB")
    for item in upload_items[:10]:
        print(f"  {item.name} ({'dir' if item.is_dir() else 'file'})")
    if len(upload_items) > 10:
        print(f"  ... and {len(upload_items) - 10} more")

print("\n=== data/outputs inspection ===")
outputs_dir = Path("data/outputs")
if outputs_dir.exists():
    output_items = list(outputs_dir.iterdir())
    print(f"Outputs count: {len(output_items)}")
    total_size = sum(f.stat().st_size for f in outputs_dir.glob("**/*") if f.is_file())
    print(f"Total outputs size: {total_size / (1024*1024):.2f} MB")
    for item in output_items[:10]:
        print(f"  {item.name} ({'dir' if item.is_dir() else 'file'})")
    if len(output_items) > 10:
        print(f"  ... and {len(output_items) - 10} more")
