"""SQLite lưu từng quả; ACK chỉ là xác nhận nhận lệnh."""

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import sqlite3
import threading
import time as clock
import uuid
from zoneinfo import ZoneInfo

LABELS = ("green", "riped", "damaged")
OUTCOMES = ("pending", "accepted", "rejected", "not_sent", "unknown")


class Store:
    def __init__(self, database, timezone_name="Asia/Bangkok", on_change=None):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.zone = ZoneInfo(timezone_name)
        self.on_change = on_change or (lambda: None)
        self._lock = threading.Lock()
        self._writer = sqlite3.connect(self.path, timeout=2, check_same_thread=False)
        self._writer.execute("PRAGMA journal_mode=WAL")
        self._writer.execute("PRAGMA synchronous=FULL")
        self._writer.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                session_id TEXT NOT NULL,
                track_id INTEGER NOT NULL,
                label TEXT NOT NULL CHECK(label IN ('green','riped','damaged')),
                confidence REAL NOT NULL,
                crossed_at TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT 'pending'
                    CHECK(outcome IN ('pending','accepted','rejected','not_sent','unknown')),
                sequence INTEGER,
                error TEXT,
                PRIMARY KEY(session_id, track_id)
            );
            CREATE INDEX IF NOT EXISTS products_crossed_at ON products(crossed_at);
        """)
        self.session_id = None
        self._session_lock = None

    def start_session(self):
        """Chỉ pipeline gọi: phiên cũ dang dở không được tự gửi lại."""
        if self._session_lock is None:
            handle = open(str(self.path) + ".pipeline.lock", "a+b")
            try:
                import os
                if os.name == "nt":
                    import msvcrt
                    if handle.tell() == 0:
                        handle.write(b"0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                handle.close()
                raise RuntimeError("Another pipeline is using this statistics database") from exc
            self._session_lock = handle
        self.session_id = str(uuid.uuid4())
        self._wall_origin = datetime.now(timezone.utc)
        self._mono_origin = clock.monotonic()
        with self._lock, self._writer:
            self._writer.execute(
                "UPDATE products SET outcome='unknown', error=? WHERE outcome='pending'",
                ("Pipeline ended before the UART outcome was recorded",),
            )
        self.on_change()

    def record(self, event):
        if self.session_id is None:
            raise RuntimeError("Statistics session has not started")
        occurred = self._wall_origin + timedelta(seconds=event.crossed_at - self._mono_origin)
        with self._lock, self._writer:
            cursor = self._writer.execute(
                "INSERT INTO products "
                "(session_id,track_id,label,confidence,crossed_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(session_id,track_id) DO NOTHING",
                (self.session_id, event.track_id, event.label, event.confidence,
                 occurred.isoformat(timespec="microseconds")),
            )
        if cursor.rowcount:
            self.on_change()

    def result(self, event, outcome, *, response=None, error=None):
        if outcome not in OUTCOMES or outcome == "pending":
            raise ValueError("Invalid final outcome")
        with self._lock, self._writer:
            cursor = self._writer.execute(
                "UPDATE products SET outcome=?, sequence=?, error=? "
                "WHERE session_id=? AND track_id=? AND outcome='pending'",
                (outcome, getattr(response, "sequence", None),
                 str(error) if error is not None else None, self.session_id, event.track_id),
            )
        if cursor.rowcount:
            self.on_change()

    def finish_session(self):
        with self._lock, self._writer:
            self._writer.execute(
                "UPDATE products SET outcome='unknown', error=? "
                "WHERE session_id=? AND outcome='pending'",
                ("Pipeline ended before the UART outcome was recorded", self.session_id),
            )
        self.on_change()

    def daily(self, start: date, end: date):
        days = (end - start).days + 1
        if not 1 <= days <= 366:
            raise ValueError("Date range must contain 1 to 366 days")
        try:
            lower = datetime.combine(start, time.min, self.zone).astimezone(timezone.utc)
            upper = datetime.combine(end + timedelta(days=1), time.min, self.zone).astimezone(timezone.utc)
        except OverflowError as exc:
            raise ValueError("Date is outside the supported UTC range") from exc
        result = {}
        for offset in range(days):
            key = (start + timedelta(days=offset)).isoformat()
            result[key] = {"date": key, "total": 0,
                           "counts": dict.fromkeys(LABELS, 0),
                           "outcomes": dict.fromkeys(OUTCOMES, 0)}
        # Đọc trên kết nối riêng; không chia sẻ cursor với luồng UART.
        connection = sqlite3.connect(self.path, timeout=2)
        try:
            rows = connection.execute(
                "SELECT crossed_at,label,outcome FROM products "
                "WHERE crossed_at>=? AND crossed_at<?",
                (lower.isoformat(timespec="microseconds"), upper.isoformat(timespec="microseconds")),
            )
            for timestamp, label, outcome in rows:
                key = datetime.fromisoformat(timestamp).astimezone(self.zone).date().isoformat()
                item = result[key]
                item["total"] += 1
                item["counts"][label] += 1
                item["outcomes"][outcome] += 1
        finally:
            connection.close()
        return list(result.values())

    def summary(self, day: date):
        result = self.daily(day, day)[0]
        result["percentages"] = {
            label: round(count * 100 / result["total"], 1) if result["total"] else 0
            for label, count in result["counts"].items()
        }
        result["timezone"] = self.zone.key
        return result

    def close(self):
        with self._lock:
            self._writer.close()
            if self._session_lock is not None:
                self._session_lock.close()
                self._session_lock = None
