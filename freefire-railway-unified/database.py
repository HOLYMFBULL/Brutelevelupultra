"""
Free Fire Persistent SQLite Database (bot.db) & Multi-Device Sync Engine
Provides:
  - SQLite bot.db storage that persists across all devices and server reboots
  - Automatic synchronization with accounts.json and accounts.js
  - Compatibility with lc.py (all_accounts_flat)
  - Safe upsert, query, and bulk export/import functions
"""

import os
import sqlite3
import json
import logging
import time

logger = logging.getLogger("FF-Database")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "bot.db")
ACCOUNTS_JSON = os.path.join(BASE_DIR, "accounts.json")
ACCOUNTS_JS = os.path.join(BASE_DIR, "accounts.js")
TOKEN_CACHE = os.path.join(BASE_DIR, "token_cache.json")


def get_db_connection(db_path=None):
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


_DB_INITIALIZED = False

def init_db(db_path=None):
    """Creates accounts and system tables in bot.db if not already present."""
    global _DB_INITIALIZED
    path = db_path or DEFAULT_DB_PATH
    conn = get_db_connection(path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT UNIQUE NOT NULL,
                    real_ff_uid TEXT,
                    nickname TEXT,
                    password TEXT,
                    region TEXT DEFAULT 'IND',
                    level INTEGER DEFAULT 1,
                    total_exp INTEGER DEFAULT 0,
                    baseline_exp INTEGER DEFAULT 0,
                    session_exp INTEGER DEFAULT 0,
                    last_match_exp INTEGER DEFAULT 0,
                    matches_played INTEGER DEFAULT 0,
                    consecutive_zero_exp INTEGER DEFAULT 0,
                    auth_type TEXT DEFAULT 'guest',
                    status TEXT DEFAULT 'IDLE',
                    device_name TEXT DEFAULT 'Samsung Galaxy S23 Ultra',
                    owner_user_id TEXT DEFAULT 'default',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS match_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    match_id TEXT,
                    mode_name TEXT,
                    exp_gained INTEGER DEFAULT 0,
                    total_exp_after INTEGER DEFAULT 0,
                    level_after INTEGER DEFAULT 1,
                    verified BOOLEAN DEFAULT 1,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
    finally:
        conn.close()

    if not _DB_INITIALIZED:
        _DB_INITIALIZED = True
        seed_if_empty(path)



def seed_if_empty(db_path=None):
    """Seeds authentic account records into bot.db if database has no accounts."""
    path = db_path or DEFAULT_DB_PATH
    conn = get_db_connection(path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        if count > 0:
            return

        # Check token_cache.json first (contains authentic Garena Major Login responses)
        cache_file = TOKEN_CACHE
        if not os.path.exists(cache_file):
            alt = os.path.join(BASE_DIR, "newbrsup", "token_cache.json")
            if os.path.exists(alt):
                cache_file = alt

        seeded = False
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for uid, info in data.items():
                    if isinstance(info, dict):
                        save_account({
                            "account_id": str(uid),
                            "real_ff_uid": str(info.get("account_id") or uid),
                            "nickname": str(info.get("nickname") or f"Player_{uid[-4:]}"),
                            "password": str(info.get("auth_password") or info.get("access_token", "")),
                            "region": str(info.get("region") or "IND"),
                            "level": int(info.get("level") or 1),
                            "total_exp": int(info.get("exp") or 0),
                            "baseline_exp": int(info.get("exp") or 0),
                            "session_exp": 0,
                            "last_match_exp": 0,
                            "matches_played": 0,
                            "consecutive_zero_exp": 0,
                            "status": "IDLE"
                        }, db_path=path)
                        seeded = True
                if seeded:
                    logger.info("Seeded bot.db from authentic token_cache.json")
            except Exception as e:
                logger.error(f"Error seeding bot.db from token_cache: {e}")

        # Fallback to accounts.json
        if not seeded and os.path.exists(ACCOUNTS_JSON):
            try:
                with open(ACCOUNTS_JSON, "r", encoding="utf-8") as f:
                    accs = json.load(f)
                for a in accs:
                    uid = str(a.get("uid") or a.get("account_id"))
                    save_account({
                        "account_id": uid,
                        "real_ff_uid": str(a.get("real_ff_uid") or uid),
                        "nickname": str(a.get("nickname") or f"Player_{uid[-4:]}"),
                        "password": str(a.get("password") or ""),
                        "region": str(a.get("region") or "IND"),
                        "level": int(a.get("level") or 1),
                        "total_exp": int(a.get("total_exp") or a.get("exp") or 0),
                        "baseline_exp": int(a.get("total_exp") or a.get("exp") or 0),
                        "session_exp": 0,
                        "last_match_exp": 0,
                        "matches_played": 0,
                        "consecutive_zero_exp": 0,
                        "status": "IDLE"
                    }, db_path=path)
            except Exception as e:
                logger.error(f"Error seeding bot.db from accounts.json: {e}")

    finally:
        conn.close()


def all_accounts_flat(db_path=None):
    """
    Called directly by lc.py line 3124:
    Return list of dicts with {"auth": {"uid": ..., "password": ...}, "auth_type": "guest", "owner_user_id": ...}
    and complete parsed metadata.
    """
    init_db(db_path)
    path = db_path or DEFAULT_DB_PATH
    conn = get_db_connection(path)
    res = []
    try:
        rows = conn.execute("SELECT * FROM accounts ORDER BY id ASC").fetchall()
        for r in rows:
            res.append({
                "account_id": r["account_id"],
                "real_ff_uid": r["real_ff_uid"],
                "nickname": r["nickname"],
                "auth_type": r["auth_type"] or "guest",
                "auth": {
                    "uid": r["account_id"],
                    "password": r["password"]
                },
                "owner_user_id": r["owner_user_id"] or "default",
                "level": r["level"],
                "total_exp": r["total_exp"],
                "session_exp": r["session_exp"],
                "region": r["region"],
                "status": r["status"]
            })
    finally:
        conn.close()
    return res


def get_all_accounts(db_path=None):
    """Returns all accounts formatted as standard dicts for engine and API."""
    init_db(db_path)
    path = db_path or DEFAULT_DB_PATH
    conn = get_db_connection(path)
    res = []
    try:
        rows = conn.execute("SELECT * FROM accounts ORDER BY id ASC").fetchall()
        for r in rows:
            res.append(dict(r))
    finally:
        conn.close()
    return res


def get_account(account_id, db_path=None):
    """Returns single account dict or None."""
    init_db(db_path)
    path = db_path or DEFAULT_DB_PATH
    conn = get_db_connection(path)
    try:
        row = conn.execute("SELECT * FROM accounts WHERE account_id = ? OR real_ff_uid = ?", (str(account_id), str(account_id))).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_account(acc, db_path=None):
    """
    Upserts account into bot.db and syncs to accounts.json and accounts.js.
    Guarantees cross-device persistence and consistent values.
    """
    init_db(db_path)
    path = db_path or DEFAULT_DB_PATH
    conn = get_db_connection(path)

    account_id = str(acc.get("account_id") or acc.get("uid") or acc.get("id")).strip()
    if not account_id:
        return False

    real_ff_uid = str(acc.get("real_ff_uid") or account_id).strip()
    nickname = str(acc.get("nickname") or f"Player_{account_id[-4:]}").strip()
    password = str(acc.get("password") or acc.get("auth_password") or "").strip()
    region = str(acc.get("region") or "IND").strip()
    level = int(acc.get("level") or 1)
    total_exp = int(acc.get("total_exp") or acc.get("exp") or 0)
    baseline_exp = int(acc.get("baseline_exp", total_exp))
    session_exp = int(acc.get("session_exp") or 0)
    last_match_exp = int(acc.get("last_match_exp") or 0)
    matches_played = int(acc.get("matches_played") or 0)
    consecutive_zero_exp = int(acc.get("consecutive_zero_exp") or 0)
    status = str(acc.get("status") or "IDLE")
    device_name = str(acc.get("device_name") or "Samsung Galaxy S23 Ultra")

    try:
        with conn:
            conn.execute("""
                INSERT INTO accounts (
                    account_id, real_ff_uid, nickname, password, region, level,
                    total_exp, baseline_exp, session_exp, last_match_exp,
                    matches_played, consecutive_zero_exp, status, device_name, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(account_id) DO UPDATE SET
                    real_ff_uid = excluded.real_ff_uid,
                    nickname = excluded.nickname,
                    password = CASE WHEN excluded.password != '' THEN excluded.password ELSE accounts.password END,
                    region = excluded.region,
                    level = excluded.level,
                    total_exp = excluded.total_exp,
                    session_exp = excluded.session_exp,
                    last_match_exp = excluded.last_match_exp,
                    matches_played = excluded.matches_played,
                    consecutive_zero_exp = excluded.consecutive_zero_exp,
                    status = excluded.status,
                    device_name = excluded.device_name,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                account_id, real_ff_uid, nickname, password, region, level,
                total_exp, baseline_exp, session_exp, last_match_exp,
                matches_played, consecutive_zero_exp, status, device_name
            ))
    finally:
        conn.close()

    # Sync to accounts.json and accounts.js
    sync_to_disk_files(path)
    return True


def update_account_stats(account_id, level, total_exp, last_match_exp, session_exp, matches_played, consecutive_zero_exp, status, db_path=None):
    """Updates live verified game stats after match verification."""
    init_db(db_path)
    path = db_path or DEFAULT_DB_PATH
    conn = get_db_connection(path)
    try:
        with conn:
            conn.execute("""
                UPDATE accounts SET
                    level = ?,
                    total_exp = ?,
                    last_match_exp = ?,
                    session_exp = ?,
                    matches_played = ?,
                    consecutive_zero_exp = ?,
                    status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ? OR real_ff_uid = ?
            """, (
                int(level), int(total_exp), int(last_match_exp), int(session_exp),
                int(matches_played), int(consecutive_zero_exp), str(status),
                str(account_id), str(account_id)
            ))
    finally:
        conn.close()

    sync_to_disk_files(path)


def delete_account(account_id, db_path=None):
    """Removes account from database and syncs disk files."""
    init_db(db_path)
    path = db_path or DEFAULT_DB_PATH
    conn = get_db_connection(path)
    try:
        with conn:
            conn.execute("DELETE FROM accounts WHERE account_id = ? OR real_ff_uid = ?", (str(account_id), str(account_id)))
    finally:
        conn.close()

    sync_to_disk_files(path)
    return True


def sync_to_disk_files(db_path=None):
    """Exports SQLite accounts directly to accounts.json and accounts.js for full file sync."""
    accounts = get_all_accounts(db_path)
    export_list = []
    for a in accounts:
        export_list.append({
            "uid": a["account_id"],
            "password": a["password"],
            "real_ff_uid": a["real_ff_uid"],
            "nickname": a["nickname"],
            "level": a["level"],
            "total_exp": a["total_exp"],
            "region": a["region"]
        })

    # Save to accounts.json in root and subdirs
    for path in [ACCOUNTS_JSON, os.path.join(BASE_DIR, "freefire-railway-unified", "accounts.json"), os.path.join(BASE_DIR, "newbrsup", "accounts.json")]:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_list, f, indent=2)
        except Exception:
            pass

    # Save to accounts.js
    js_content = "module.exports = " + json.dumps(export_list, indent=2) + ";\n"
    for path in [ACCOUNTS_JS, os.path.join(BASE_DIR, "freefire-railway-unified", "accounts.js")]:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(js_content)
        except Exception:
            pass


# Automatically ensure DB on module import
init_db()
