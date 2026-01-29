import sqlite3
from datetime import date
from typing import Optional, Dict, Any, List, Tuple

class ParkingDB:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def init(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            date_key TEXT NOT NULL,      -- YYYY-MM-DD
            action TEXT NOT NULL,        -- IN / OUT
            vehicle_type TEXT NOT NULL,  -- motorbike / car
            plate_canonical TEXT NOT NULL,
            plate_display TEXT,
            fee INTEGER DEFAULT 0,
            img_path TEXT,
            crop_path TEXT
        )
        """)

        # Nếu DB cũ thiếu cột -> tự add (migrate đơn giản)
        cols = {r[1] for r in cur.execute("PRAGMA table_info(events)").fetchall()}
        if "vehicle_type" not in cols:
            cur.execute("ALTER TABLE events ADD COLUMN vehicle_type TEXT NOT NULL DEFAULT 'motorbike'")
        if "fee" not in cols:
            cur.execute("ALTER TABLE events ADD COLUMN fee INTEGER DEFAULT 0")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_date_plate ON events(date_key, plate_canonical)")
        conn.commit()
        conn.close()

    def insert_event(self, ts: str, action: str, vehicle_type: str,
                     plate_canon: str, plate_display: str, fee: int,
                     img_path: str, crop_path: str) -> None:
        date_key = ts[:10]
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO events (ts, date_key, action, vehicle_type, plate_canonical, plate_display, fee, img_path, crop_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, date_key, action, vehicle_type, plate_canon, plate_display, int(fee), img_path, crop_path))
        conn.commit()
        conn.close()

    def latest_event_today(self, plate_canon: str) -> Optional[Dict[str, Any]]:
        today = date.today().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM events
            WHERE date_key = ? AND plate_canonical = ?
            ORDER BY id DESC
            LIMIT 1
        """, (today, plate_canon))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def latest_in_today(self, plate_canon: str) -> Optional[Dict[str, Any]]:
        today = date.today().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM events
            WHERE date_key = ? AND plate_canonical = ? AND action='IN'
            ORDER BY id DESC
            LIMIT 1
        """, (today, plate_canon))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def today_summary(self) -> Tuple[int, Dict[str, int]]:
        today = date.today().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("""
            SELECT COALESCE(SUM(fee), 0)
            FROM events
            WHERE date_key = ? AND action='OUT'
        """, (today,))
        total_fee = int(cur.fetchone()[0] or 0)

        cur.execute("""
            SELECT vehicle_type, COUNT(*)
            FROM events
            WHERE date_key = ? AND action='OUT'
            GROUP BY vehicle_type
        """, (today,))
        counts = {k: int(v) for k, v in cur.fetchall()}

        conn.close()
        return total_fee, counts

    def recent_events(self, limit: int = 20) -> List[Tuple]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT ts, action, vehicle_type, plate_display, plate_canonical, fee, img_path, crop_path
            FROM events
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        return rows
