import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "branches_data.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        branch_name TEXT NOT NULL,
        employee_name TEXT,
        doc_type TEXT NOT NULL, -- 'بطاقة شخصية' أو 'فك باسورد زيروتك'
        unique_id TEXT NOT NULL, -- الرقم القومي أو السيريال نمبر
        title_or_name TEXT, -- الاسم الكامل أو موديل الجهاز
        secondary_data TEXT, -- كود الفك / تاريخ الجهاز / العنوان
        all_details TEXT, -- JSON أو نص تفصيلي لكافة البيانات
        image_path TEXT,
        is_duplicate INTEGER DEFAULT 0, -- 0 = جديد، 1 = مكرر
        duplicate_note TEXT,
        google_synced INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_unique_id ON records (unique_id);
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    conn.commit()
    conn.close()

def check_duplicate(unique_id: str, doc_type: str = None) -> Optional[Dict[str, Any]]:
    """
    يفحص ما إذا كان الرقم الفريد (الرقم القومي أو السيريال) مسجلاً مسبقاً
    """
    if not unique_id or len(unique_id.strip()) < 4:
        return None
    
    clean_id = unique_id.strip()
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT * FROM records 
    WHERE unique_id = ? 
    ORDER BY created_at ASC 
    LIMIT 1
    """
    cursor.execute(query, (clean_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def add_record(
    branch_name: str,
    doc_type: str,
    unique_id: str,
    title_or_name: str,
    secondary_data: str = "",
    all_details: str = "",
    image_path: str = "",
    employee_name: str = "",
    is_duplicate: bool = False,
    duplicate_note: str = ""
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO records (
        branch_name, employee_name, doc_type, unique_id, title_or_name,
        secondary_data, all_details, image_path, is_duplicate, duplicate_note
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        branch_name, employee_name, doc_type, unique_id.strip(), title_or_name,
        secondary_data, all_details, image_path, 1 if is_duplicate else 0, duplicate_note
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id

def get_records(limit: int = 100, branch: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    if branch and branch != "الكل":
        cursor.execute("""
        SELECT * FROM records 
        WHERE branch_name = ? 
        ORDER BY created_at DESC 
        LIMIT ?
        """, (branch, limit))
    else:
        cursor.execute("""
        SELECT * FROM records 
        ORDER BY created_at DESC 
        LIMIT ?
        """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_synced(record_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE records SET google_synced = 1 WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO settings (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()

# تهيئة قاعدة البيانات تلقائياً عند استيراد الملف
init_db()
