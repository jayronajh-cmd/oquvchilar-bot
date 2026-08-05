# -*- coding: utf-8 -*-
"""
SQLite ma'lumotlar bazasi bilan ishlash uchun barcha funksiyalar shu yerda.
"""
import sqlite3
from datetime import date, datetime
from contextlib import contextmanager

from config import DB_PATH

# ---------------------------------------------------------------------------


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oquvchilar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ism_familiya TEXT NOT NULL,
                yonalish TEXT NOT NULL,
                jinsi TEXT NOT NULL,
                holati TEXT NOT NULL DEFAULT 'faol',   -- faol / ketgan / sababli
                qoshilgan_sana TEXT NOT NULL,
                ketgan_sana TEXT,
                sabab TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tarix (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                oquvchi_id INTEGER NOT NULL,
                harakat TEXT NOT NULL,   -- qoshildi / ketdi / qaytdi
                sana TEXT NOT NULL,
                izoh TEXT,
                FOREIGN KEY (oquvchi_id) REFERENCES oquvchilar (id)
            )
            """
        )


def _today():
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Qo'shish


def add_student(ism_familiya, yonalish, jinsi):
    today = _today()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO oquvchilar (ism_familiya, yonalish, jinsi, holati, qoshilgan_sana)
               VALUES (?, ?, ?, 'faol', ?)""",
            (ism_familiya, yonalish, jinsi, today),
        )
        student_id = cur.lastrowid
        conn.execute(
            "INSERT INTO tarix (oquvchi_id, harakat, sana, izoh) VALUES (?, 'qoshildi', ?, ?)",
            (student_id, today, None),
        )
        return student_id


# ---------------------------------------------------------------------------
# Qidirish / ro'yxatlar


def search_students(query, holatlar=None):
    """Ism-familiya bo'yicha qidiradi. holatlar - masalan ['faol'] yoki None (hammasi)."""
    sql = "SELECT * FROM oquvchilar WHERE ism_familiya LIKE ?"
    params = [f"%{query}%"]
    if holatlar:
        placeholders = ",".join("?" * len(holatlar))
        sql += f" AND holati IN ({placeholders})"
        params.extend(holatlar)
    sql += " ORDER BY ism_familiya"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def get_list(holati=None, yonalish=None):
    sql = "SELECT * FROM oquvchilar WHERE 1=1"
    params = []
    if holati:
        sql += " AND holati = ?"
        params.append(holati)
    if yonalish:
        sql += " AND yonalish = ?"
        params.append(yonalish)
    sql += " ORDER BY ism_familiya"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def get_student(student_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM oquvchilar WHERE id = ?", (student_id,)).fetchone()
        tarix = conn.execute(
            "SELECT * FROM tarix WHERE oquvchi_id = ? ORDER BY sana, id", (student_id,)
        ).fetchall()
        return row, tarix


# ---------------------------------------------------------------------------
# Holat o'zgartirish


def mark_left(student_id, turi, sabab=None):
    """turi: 'butunlay' -> holati='ketgan', 'vaqtincha' -> holati='sababli'"""
    holati = "ketgan" if turi == "butunlay" else "sababli"
    today = _today()
    with get_conn() as conn:
        conn.execute(
            "UPDATE oquvchilar SET holati = ?, ketgan_sana = ?, sabab = ? WHERE id = ?",
            (holati, today, sabab, student_id),
        )
        conn.execute(
            "INSERT INTO tarix (oquvchi_id, harakat, sana, izoh) VALUES (?, 'ketdi', ?, ?)",
            (student_id, today, sabab),
        )


def mark_returned(student_id):
    today = _today()
    with get_conn() as conn:
        conn.execute(
            """UPDATE oquvchilar
               SET holati = 'faol', qoshilgan_sana = ?, ketgan_sana = NULL, sabab = NULL
               WHERE id = ?""",
            (today, student_id),
        )
        conn.execute(
            "INSERT INTO tarix (oquvchi_id, harakat, sana, izoh) VALUES (?, 'qaytdi', ?, ?)",
            (student_id, today, None),
        )


def delete_student(student_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM tarix WHERE oquvchi_id = ?", (student_id,))
        conn.execute("DELETE FROM oquvchilar WHERE id = ?", (student_id,))


# ---------------------------------------------------------------------------
# Statistika


def get_stats():
    with get_conn() as conn:
        faol = conn.execute("SELECT * FROM oquvchilar WHERE holati = 'faol'").fetchall()
        ketgan = conn.execute("SELECT * FROM oquvchilar WHERE holati = 'ketgan'").fetchall()
        sababli = conn.execute("SELECT * FROM oquvchilar WHERE holati = 'sababli'").fetchall()

    ogil = sum(1 for s in faol if s["jinsi"] == "ogil")
    qiz = sum(1 for s in faol if s["jinsi"] == "qiz")

    yonalish_taqsimot = {}
    for s in faol:
        yonalish_taqsimot[s["yonalish"]] = yonalish_taqsimot.get(s["yonalish"], 0) + 1

    return {
        "jami_faol": len(faol),
        "ogil": ogil,
        "qiz": qiz,
        "yonalish_taqsimot": yonalish_taqsimot,
        "ketgan_soni": len(ketgan),
        "sababli_soni": len(sababli),
    }


def kun_farqi(sana1, sana2=None):
    """Ikki ISO-sana orasidagi kunlar sonini qaytaradi."""
    d1 = datetime.strptime(sana1, "%Y-%m-%d").date()
    d2 = datetime.strptime(sana2, "%Y-%m-%d").date() if sana2 else date.today()
    return (d2 - d1).days
