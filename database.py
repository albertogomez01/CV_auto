import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = os.getenv("DATABASE_PATH", "jobs.db")
IS_POSTGRES = bool(DATABASE_URL)

if IS_POSTGRES:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        IS_POSTGRES = False

def get_connection():
    if IS_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def get_cursor(conn):
    if IS_POSTGRES:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()

def format_sql(sql: str) -> str:
    if IS_POSTGRES:
        return sql.replace("?", "%s")
    return sql

def init_db():
    conn = get_connection()
    try:
        cursor = get_cursor(conn)
        
        # 1. Tabla de Usuarios para multiusuario Telegram
        sql_users = """
            CREATE TABLE IF NOT EXISTS users (
                chat_id TEXT PRIMARY KEY,
                username TEXT,
                job_title TEXT,
                location TEXT,
                cv_text TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT
            )
        """
        cursor.execute(format_sql(sql_users))

        # 2. Tabla de Aplicaciones / Vacantes evaluadas
        sql_apps = """
            CREATE TABLE IF NOT EXISTS applications (
                job_id TEXT,
                user_id TEXT DEFAULT '',
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
                killer_answers TEXT,
                PRIMARY KEY (job_id, user_id)
            )
        """
        cursor.execute(format_sql(sql_apps))

        # Migraciones dinámicas para tablas SQLite existentes (si no es Postgres)
        if not IS_POSTGRES:
            cursor.execute("PRAGMA table_info(applications)")
            existing_cols = [row[1] for row in cursor.fetchall()]
            for col_name in ["salary", "location", "modality", "sector", "platform", "user_id"]:
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE applications ADD COLUMN {col_name} TEXT DEFAULT ''")
        
        conn.commit()
    finally:
        conn.close()

# --- FUNCIONES DE USUARIOS (MULTIUSER) ---

def upsert_user(
    chat_id: str,
    username: Optional[str] = "",
    job_title: Optional[str] = "",
    location: Optional[str] = "",
    cv_text: Optional[str] = "",
    active: int = 1
) -> Dict[str, Any]:
    cid_str = str(chat_id)
    now_str = datetime.now().isoformat()
    conn = get_connection()
    try:
        cursor = get_cursor(conn)
        sql = """
            INSERT INTO users (chat_id, username, job_title, location, cv_text, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                username = CASE WHEN excluded.username != '' THEN excluded.username ELSE users.username END,
                job_title = CASE WHEN excluded.job_title != '' THEN excluded.job_title ELSE users.job_title END,
                location = CASE WHEN excluded.location != '' THEN excluded.location ELSE users.location END,
                cv_text = CASE WHEN excluded.cv_text != '' THEN excluded.cv_text ELSE users.cv_text END,
                active = excluded.active
        """
        cursor.execute(format_sql(sql), (cid_str, username or "", job_title or "", location or "", cv_text or "", active, now_str))
        conn.commit()
        return get_user(cid_str) or {}
    finally:
        conn.close()

def get_user(chat_id: str) -> Optional[Dict[str, Any]]:
    cid_str = str(chat_id)
    conn = get_connection()
    try:
        cursor = get_cursor(conn)
        sql = "SELECT * FROM users WHERE chat_id = ?"
        cursor.execute(format_sql(sql), (cid_str,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_active_users() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = get_cursor(conn)
        sql = "SELECT * FROM users WHERE active = 1 ORDER BY created_at DESC"
        cursor.execute(format_sql(sql))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def set_user_active(chat_id: str, active: int) -> bool:
    cid_str = str(chat_id)
    conn = get_connection()
    try:
        cursor = get_cursor(conn)
        sql = "UPDATE users SET active = ? WHERE chat_id = ?"
        cursor.execute(format_sql(sql), (active, cid_str))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

# --- FUNCIONES DE APLICACIONES Y DEDUPLICACIÓN ---

def is_job_processed(
    job_id: Optional[str] = None,
    link: Optional[str] = None,
    title: Optional[str] = None,
    company: Optional[str] = None,
    user_id: Optional[str] = None
) -> bool:
    uid_str = str(user_id) if user_id else ""
    conn = get_connection()
    try:
        cursor = get_cursor(conn)
        
        # 1. Comprobar por ID exacto de la vacante para este usuario
        if job_id:
            if uid_str:
                sql = "SELECT 1 FROM applications WHERE job_id = ? AND (user_id = ? OR user_id = '')"
                cursor.execute(format_sql(sql), (job_id, uid_str))
            else:
                sql = "SELECT 1 FROM applications WHERE job_id = ?"
                cursor.execute(format_sql(sql), (job_id,))
            if cursor.fetchone() is not None:
                return True

        # 2. Comprobar por URL/enlace directo
        if link and len(link) > 5:
            if uid_str:
                sql = "SELECT 1 FROM applications WHERE link = ? AND (user_id = ? OR user_id = '')"
                cursor.execute(format_sql(sql), (link, uid_str))
            else:
                sql = "SELECT 1 FROM applications WHERE link = ?"
                cursor.execute(format_sql(sql), (link,))
            if cursor.fetchone() is not None:
                return True

        # 3. Comprobar por par Título + Empresa para este usuario
        if title and company and len(title) > 3 and len(company) > 2:
            if uid_str:
                sql = "SELECT 1 FROM applications WHERE LOWER(TRIM(title)) = LOWER(TRIM(?)) AND LOWER(TRIM(company)) = LOWER(TRIM(?)) AND (user_id = ? OR user_id = '')"
                cursor.execute(format_sql(sql), (title, company, uid_str))
            else:
                sql = "SELECT 1 FROM applications WHERE LOWER(TRIM(title)) = LOWER(TRIM(?)) AND LOWER(TRIM(company)) = LOWER(TRIM(?))"
                cursor.execute(format_sql(sql), (title, company))
            if cursor.fetchone() is not None:
                return True

        return False
    finally:
        conn.close()

def update_job_status(job_identifier: str, status: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    import hashlib
    uid_str = str(user_id) if user_id else ""
    conn = get_connection()
    try:
        cursor = get_cursor(conn)
        if uid_str:
            sql = "SELECT * FROM applications WHERE job_id = ? AND user_id = ?"
            cursor.execute(format_sql(sql), (job_identifier, uid_str))
        else:
            sql = "SELECT * FROM applications WHERE job_id = ?"
            cursor.execute(format_sql(sql), (job_identifier,))
        row = cursor.fetchone()
        
        if not row:
            sql_all = "SELECT * FROM applications"
            cursor.execute(format_sql(sql_all))
            rows = cursor.fetchall()
            for r in rows:
                r_dict = dict(r)
                j_id = str(r_dict.get("job_id", ""))
                h = hashlib.md5(j_id.encode("utf-8")).hexdigest()[:16]
                if h == job_identifier or j_id == job_identifier:
                    row = r
                    break
        
        if row:
            r_dict = dict(row)
            target_id = r_dict["job_id"]
            target_uid = r_dict.get("user_id", "")
            sql_upd = "UPDATE applications SET status = ? WHERE job_id = ? AND user_id = ?"
            cursor.execute(format_sql(sql_upd), (status, target_id, target_uid))
            conn.commit()
            cursor.execute(format_sql("SELECT * FROM applications WHERE job_id = ? AND user_id = ?"), (target_id, target_uid))
            updated_row = cursor.fetchone()
            return dict(updated_row) if updated_row else r_dict
        return None
    finally:
        conn.close()

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
    platform: Optional[str] = None,
    user_id: Optional[str] = None
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
        platform=platform,
        user_id=user_id
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
    killer_answers: Optional[List[Dict[str, Any]]] = None,
    user_id: Optional[str] = None
):
    date_str = datetime.now().isoformat()
    answers_json = json.dumps(killer_answers) if killer_answers else None
    uid_str = str(user_id) if user_id else ""
    
    conn = get_connection()
    try:
        cursor = get_cursor(conn)
        sql = """
            INSERT INTO applications (job_id, user_id, title, company, link, score, status, date_applied, salary, location, modality, sector, platform, killer_answers)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, user_id) DO UPDATE SET
                score = excluded.score,
                status = excluded.status,
                date_applied = excluded.date_applied,
                salary = excluded.salary,
                location = excluded.location,
                modality = excluded.modality,
                sector = excluded.sector,
                platform = excluded.platform,
                killer_answers = excluded.killer_answers
        """
        cursor.execute(format_sql(sql), (job_id, uid_str, title, company, link, score, status, date_str, salary or "", location or "", modality or "", sector or "", platform or "", answers_json or ""))
        conn.commit()
    finally:
        conn.close()

def get_all_applications(limit: int = 100, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    uid_str = str(user_id) if user_id else ""
    conn = get_connection()
    try:
        cursor = get_cursor(conn)
        if uid_str:
            sql = "SELECT job_id, user_id, title, company, link, score, status, date_applied, salary, location, modality, sector, platform, killer_answers FROM applications WHERE user_id = ? ORDER BY date_applied DESC LIMIT ?"
            cursor.execute(format_sql(sql), (uid_str, limit))
        else:
            sql = "SELECT job_id, user_id, title, company, link, score, status, date_applied, salary, location, modality, sector, platform, killer_answers FROM applications ORDER BY date_applied DESC LIMIT ?"
            cursor.execute(format_sql(sql), (limit,))
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
    finally:
        conn.close()

# Auto initialize DB on module import
init_db()
