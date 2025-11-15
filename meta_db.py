import sqlite3

import config

DB = sqlite3.connect(config.DB_PATH, check_same_thread=False)
DB.row_factory = sqlite3.Row

DB.execute(
    """
CREATE TABLE IF NOT EXISTS image_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE,
    record_found INTEGER DEFAULT 0,
    recorded INTEGER DEFAULT 0,
    not_found INTEGER DEFAULT 0,
    payment_record INTEGER DEFAULT 0,
    note TEXT DEFAULT ''
)
"""
)
DB.commit()


def meta_key(chat_id: str, filename: str) -> str:
    return f"{chat_id}::{filename}"


def get_image_meta(chat_id: str, filename: str):
    key = meta_key(chat_id, filename)
    cur = DB.execute(
        "SELECT record_found, recorded, not_found, payment_record, note "
        "FROM image_meta WHERE filename = ?",
        (key,),
    )
    row = cur.fetchone()
    if not row:
        return {
            "record_found": 0,
            "recorded": 0,
            "not_found": 0,
            "payment_record": 0,
            "note": "",
        }
    return {
        "record_found": int(row["record_found"]),
        "recorded": int(row["recorded"]),
        "not_found": int(row["not_found"]),
        "payment_record": int(row["payment_record"]),
        "note": row["note"] or "",
    }


def save_image_meta(
    chat_id: str,
    filename: str,
    record_found: int,
    recorded: int,
    not_found: int,
    payment_record: int,
    note: str,
):
    key = meta_key(chat_id, filename)
    DB.execute(
        """
        INSERT INTO image_meta (filename, record_found, recorded, not_found, payment_record, note)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(filename) DO UPDATE SET
            record_found = excluded.record_found,
            recorded = excluded.recorded,
            not_found = excluded.not_found,
            payment_record = excluded.payment_record,
            note = excluded.note
        """,
        (key, record_found, recorded, not_found, payment_record, note),
    )
    DB.commit()
