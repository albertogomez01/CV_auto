import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "jobs.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                job_id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                link TEXT,
                score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                date_applied TEXT,
                salary TEXT,
                location TEXT,
                modality TEXT,
                sector TEXT,
                platform TEXT,
                killer_answers TEXT
            )
        """)
        # Schema migration check for existing databases
        cursor.execute("PRAGMA table_info(applications)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        for col_name in ["salary", "location", "modality", "sector", "platform"]:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE applications ADD COLUMN {col_name} TEXT")
        conn.commit()

def is_job_processed(job_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM applications WHERE job_id = ? AND status IN ('applied', 'success', 'already_applied', 'already_applied_on_site', 'discarded', 'descartada')", (job_id,))
        return cursor.fetchone() is not None

def discard_job(
    job_id: str,
    title: str,
    company: str,
    link: str,
    score: int = 0,
    salary: Optional[str] = None,
    location: Optional[str] = None,
    modality: Optional[str] = None,
    sector: Optional[str] = None,
    platform: Optional[str] = None
):
    record_application(
        job_id=job_id,
        title=title,
        company=company,
        link=link,
        score=score,
        status="descartada",
        salary=salary,
        location=location,
        modality=modality,
        sector=sector,
        platform=platform
    )

def record_application(
    job_id: str,
    title: str,
    company: str,
    link: str,
    score: int = 0,
    status: str = "applied",
    salary: Optional[str] = None,
    location: Optional[str] = None,
    modality: Optional[str] = None,
    sector: Optional[str] = None,
    platform: Optional[str] = None,
    killer_answers: Optional[List[Dict[str, Any]]] = None
):
    date_str = datetime.now().isoformat()
    answers_json = json.dumps(killer_answers) if killer_answers else None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO applications (job_id, title, company, link, score, status, date_applied, salary, location, modality, sector, platform, killer_answers)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                score = excluded.score,
                status = excluded.status,
                date_applied = excluded.date_applied,
                salary = excluded.salary,
                location = excluded.location,
                modality = excluded.modality,
                sector = excluded.sector,
                platform = excluded.platform,
                killer_answers = excluded.killer_answers
        """, (job_id, title, company, link, score, status, date_str, salary, location, modality, sector, platform, answers_json))
        conn.commit()

def get_all_applications(limit: int = 100) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT job_id, title, company, link, score, status, date_applied, salary, location, modality, sector, platform, killer_answers FROM applications ORDER BY date_applied DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get("killer_answers"):
                try:
                    item["killer_answers"] = json.loads(item["killer_answers"])
                except Exception:
                    pass
            result.append(item)
        return result

# Auto initialize DB on module import
init_db()
