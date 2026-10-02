"""
Feedback Module — Patient Feedback & Satisfaction Tracking
===========================================================
DB operations for collecting and analyzing patient feedback.

Tables:
    feedback — Individual feedback entries (rating, category, comments)
    feedback_stats — Aggregated daily stats per department (for dashboards)

Coordinates: One feedback entry per test completion.
"""
import uuid
from datetime import date, datetime

from utils.db import (
    USE_GOOGLE_SHEETS, USE_SUPABASE, USE_LOCAL_JSON, _gs_failed,
    call_gs_api, get_client, DB_FILE
)
import sqlite3

# ─── JSON fallback (lazy import) ──────────────────────────────────────────────
_json_module = None


def _get_json():
    global _json_module
    if _json_module is None and USE_LOCAL_JSON:
        from utils import local_json_db
        _json_module = local_json_db
    return _json_module


# ─── SCHEMA INIT ──────────────────────────────────────────────────────────────

def _init_feedback_tables():
    """Create feedback tables in SQLite if they don't exist."""
    if USE_SUPABASE or USE_GOOGLE_SHEETS:
        return  # Tables handled separately for those backends
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                test_id TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                category TEXT NOT NULL DEFAULT 'general',
                comments TEXT DEFAULT '',
                acknowledged INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
                FOREIGN KEY (test_id) REFERENCES tests(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_stats (
                id TEXT PRIMARY KEY,
                dept_name TEXT NOT NULL,
                stat_date TEXT NOT NULL,
                total_count INTEGER DEFAULT 0,
                avg_rating REAL DEFAULT 0.0,
                rating_1 INTEGER DEFAULT 0,
                rating_2 INTEGER DEFAULT 0,
                rating_3 INTEGER DEFAULT 0,
                rating_4 INTEGER DEFAULT 0,
                rating_5 INTEGER DEFAULT 0,
                UNIQUE(dept_name, stat_date)
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"[FeedbackDB] init error: {e}")
    finally:
        conn.close()


# Initialize on import
_init_feedback_tables()


# ─── FEEDBACK CATEGORIES ──────────────────────────────────────────────────────

FEEDBACK_CATEGORIES = [
    ("general", "😊 General Experience"),
    ("wait_time", "⏳ Wait Time"),
    ("staff_behavior", "🤝 Staff Behaviour"),
    ("cleanliness", "🧹 Cleanliness"),
    ("facilities", "🏥 Facilities"),
    ("doctor", "👨‍⚕️ Doctor Consultation"),
]


def submit_feedback(patient_id: str, test_id: str, rating: int,
                    category: str = "general", comments: str = "") -> dict:
    """
    Submit a feedback entry for a completed test.

    Args:
        patient_id: Patient's public ID (e.g. CQ-20260711-001)
        test_id: Test record UUID
        rating: 1-5 star rating
        category: One of FEEDBACK_CATEGORIES keys
        comments: Optional text comments

    Returns:
        dict with "success" bool and "message" string
    """
    # Validate rating
    if rating < 1 or rating > 5:
        return {"success": False, "message": "Rating must be between 1 and 5."}

    # Validate category
    valid_cats = [c[0] for c in FEEDBACK_CATEGORIES]
    if category not in valid_cats:
        return {"success": False, "message": f"Invalid category. Choose from: {', '.join(valid_cats)}"}

    now_str = datetime.now().isoformat()
    feedback_id = str(uuid.uuid4())

    # ─── Google Sheets ────────────────────────────────────────────────────────
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("submitFeedback", {
            "id": feedback_id,
            "patient_id": patient_id,
            "test_id": test_id,
            "rating": rating,
            "category": category,
            "comments": comments,
            "created_at": now_str,
        }, is_post=True)
        if res:
            _update_feedback_stats_gs(test_id, rating)
            return {"success": True, "message": "✅ Feedback submitted. Thank you!"}
        # Fall through to Local JSON

    # ─── Local JSON ───────────────────────────────────────────────────────────
    json_mod = _get_json()
    if json_mod:
        result = json_mod.submit_feedback_json(patient_id, test_id, rating, category, comments)
        if result["success"]:
            json_mod.update_feedback_stats_json(test_id, rating)
        return result

    # ─── SQLite / Supabase ────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            data = {
                "id": feedback_id,
                "patient_id": patient_id,
                "test_id": test_id,
                "rating": rating,
                "category": category,
                "comments": comments,
                "created_at": now_str,
            }
            get_client().table("feedback").insert(data).execute()
            _update_feedback_stats_supabase(test_id, rating)
            return {"success": True, "message": "✅ Feedback submitted. Thank you!"}
        except Exception as e:
            print(f"[FeedbackDB] Supabase error: {e}")
            return {"success": False, "message": "❌ Failed to submit feedback."}
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO feedback (id, patient_id, test_id, rating, category, comments, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (feedback_id, patient_id, test_id, rating, category, comments, now_str)
            )
            conn.commit()
            _update_feedback_stats_sqlite(conn, test_id, rating)
            return {"success": True, "message": "✅ Feedback submitted. Thank you!"}
        except Exception as e:
            print(f"[FeedbackDB] SQLite error: {e}")
            return {"success": False, "message": "❌ Failed to submit feedback."}
        finally:
            conn.close()


def get_feedback_for_test(test_id: str) -> dict | None:
    """Get feedback for a specific test record."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_feedback_for_test_json(test_id)

    if USE_SUPABASE:
        try:
            res = get_client().table("feedback").select("*").eq("test_id", test_id).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception:
            return None
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM feedback WHERE test_id=? LIMIT 1", (test_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
        except Exception:
            return None
        finally:
            conn.close()


def get_all_feedback(limit: int = 50, dept: str = "", min_rating: int = 0) -> list[dict]:
    """
    Get feedback entries with optional filters.
    Joins with patients table to get patient name.
    """
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_all_feedback_json(limit, dept, min_rating)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = """
            SELECT f.*, p.name AS patient_name, t.test_name
            FROM feedback f
            LEFT JOIN patients p ON f.patient_id = p.patient_id
            LEFT JOIN tests t ON f.test_id = t.id
            WHERE 1=1
        """
        params = []
        if dept:
            query += " AND t.test_name=?"
            params.append(dept)
        if min_rating > 0:
            query += " AND f.rating>=?"
            params.append(min_rating)
        query += " ORDER BY f.created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"[FeedbackDB] get_all error: {e}")
        return []
    finally:
        conn.close()


def get_feedback_stats(start_date: str = "", end_date: str = "") -> list[dict]:
    """
    Get aggregated feedback stats per department for date range.
    Returns: [{"dept_name": str, "total_count": int, "avg_rating": float, ...}]
    """
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_feedback_stats_json(start_date, end_date)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = """
            SELECT dept_name,
                   SUM(total_count) AS total_count,
                   CASE WHEN SUM(total_count) > 0
                        THEN ROUND(CAST(SUM(total_count * avg_rating) AS REAL) / SUM(total_count), 1)
                        ELSE 0.0
                   END AS avg_rating,
                   SUM(rating_1) AS rating_1,
                   SUM(rating_2) AS rating_2,
                   SUM(rating_3) AS rating_3,
                   SUM(rating_4) AS rating_4,
                   SUM(rating_5) AS rating_5
            FROM feedback_stats
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND stat_date>=?"
            params.append(start_date)
        if end_date:
            query += " AND stat_date<=?"
            params.append(end_date)
        query += " GROUP BY dept_name ORDER BY total_count DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"[FeedbackDB] stats error: {e}")
        return []
    finally:
        conn.close()


def acknowledge_feedback(feedback_id: str) -> bool:
    """Mark a feedback entry as acknowledged by staff."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.acknowledge_feedback_json(feedback_id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE feedback SET acknowledged=1 WHERE id=?", (feedback_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


# ─── INTERNAL: Update feedback_stats ─────────────────────────────────────────

def _update_feedback_stats_sqlite(conn, test_id: str, rating: int):
    """Update or create a feedback_stats entry for the department of test_id."""
    try:
        cursor = conn.cursor()
        # Get test's department
        cursor.execute("SELECT test_name FROM tests WHERE id=?", (test_id,))
        row = cursor.fetchone()
        if not row:
            return
        dept = row[0]
        today = date.today().isoformat()

        cursor.execute(
            "SELECT id, total_count, avg_rating FROM feedback_stats WHERE dept_name=? AND stat_date=?",
            (dept, today)
        )
        existing = cursor.fetchone()

        if existing:
            stat_id, total, avg = existing
            new_total = total + 1
            new_avg = round(((avg * total) + rating) / new_total, 1)
            update_sql = """
                UPDATE feedback_stats
                SET total_count=?, avg_rating=?,
                    rating_? = rating_? + 1
                WHERE id=?
            """
            cursor.execute(
                f"UPDATE feedback_stats SET total_count=?, avg_rating=?, "
                f"rating_{rating}=rating_{rating}+1 WHERE id=?",
                (new_total, new_avg, stat_id)
            )
        else:
            stat_id = str(uuid.uuid4())
            rating_cols = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            rating_cols[rating] = 1
            cursor.execute(
                "INSERT INTO feedback_stats (id, dept_name, stat_date, total_count, avg_rating, "
                "rating_1, rating_2, rating_3, rating_4, rating_5) "
                "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
                (stat_id, dept, today, float(rating),
                 rating_cols[1], rating_cols[2], rating_cols[3],
                 rating_cols[4], rating_cols[5])
            )
        conn.commit()
    except Exception as e:
        print(f"[FeedbackDB] stats update error: {e}")


def _update_feedback_stats_supabase(test_id: str, rating: int):
    """Update feedback stats in Supabase."""
    try:
        client = get_client()
        res = client.table("tests").select("test_name").eq("id", test_id).limit(1).execute()
        if not res.data:
            return
        dept = res.data[0]["test_name"]
        today = date.today().isoformat()

        existing = client.table("feedback_stats") \
            .select("*") \
            .eq("dept_name", dept) \
            .eq("stat_date", today) \
            .limit(1) \
            .execute()

        if existing.data:
            row = existing.data[0]
            new_total = row["total_count"] + 1
            new_avg = round(((row["avg_rating"] * row["total_count"]) + rating) / new_total, 1)
            rating_key = f"rating_{rating}"
            client.table("feedback_stats") \
                .update({
                    "total_count": new_total,
                    "avg_rating": new_avg,
                    rating_key: row[rating_key] + 1
                }) \
                .eq("id", row["id"]) \
                .execute()
        else:
            stat_id = str(uuid.uuid4())
            rating_map = {f"rating_{i}": (1 if i == rating else 0) for i in range(1, 6)}
            client.table("feedback_stats").insert({
                "id": stat_id, "dept_name": dept, "stat_date": today,
                "total_count": 1, "avg_rating": float(rating),
                **rating_map
            }).execute()
    except Exception as e:
        print(f"[FeedbackDB] Supabase stats error: {e}")


def _update_feedback_stats_gs(test_id: str, rating: int):
    """Update feedback stats for Google Sheets."""
    # Google Sheets handles aggregation via sheet formulas; no-op here.
    pass
