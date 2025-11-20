from __future__ import annotations

from sqlalchemy import inspect, text
from flask import current_app

from webapp.db import db


def db_can_write() -> bool:
    """Probe DB to determine if writes are allowed on this connection."""
    try:
        with db.engine.connect() as conn:
            ro = conn.execute(text("SHOW transaction_read_only")).scalar()
            return str(ro).lower() in ("off", "false", "0")
    except Exception as e:
        print(f"[db] read-only probe failed: {e}", flush=True)
        return False


def ensure_documents_table(app=None):
    """
    Create schema once if missing and DB is writable.
    Skip silently on read-only endpoints.
    """
    app = app or current_app
    try:
        with app.app_context():
            insp = inspect(db.engine)
            if "Documents" in insp.get_table_names():
                return
            if db_can_write():
                print("[db] Creating schema via create_all()", flush=True)
                db.create_all()
            else:
                print(
                    "[db]table missing,DB is read-only; skipping create_all()",
                    flush=True,
                )
    except Exception as e:
        print(f"[db] ensure schema failed: {e}", flush=True)


def ensure_documents_columns(app=None):
    app = app or current_app
    try:
        with app.app_context():
            insp = inspect(db.engine)
            if "Documents" not in insp.get_table_names():
                return
            cols = {c["name"] for c in insp.get_columns("Documents")}
            alters = []

            base = (
                'ALTER TABLE "Documents" '
                "ADD COLUMN IF NOT EXISTS {} {} NULL"
            )
            elsetext = (
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                'documents_path_uidx ON "Documents"(path)'
            )

            if "doc_type" not in cols:
                alters.append(base.format("doc_type", "varchar"))
            if "date_planned_review" not in cols:
                alters.append(base.format("date_planned_review", "date"))
            if "owner" not in cols:
                alters.append(base.format("owner", "varchar"))
            if "doc_metadata" not in cols:
                alters.append(base.format("doc_metadata", "json"))
            if "headings_map" not in cols:
                alters.append(base.format("headings_map", "json"))

            if alters and db_can_write():
                with db.engine.begin() as conn:
                    for stmt in alters:
                        conn.execute(text(stmt))
                # Ensure unique index on path
                with db.engine.begin() as conn:
                    conn.execute(text(elsetext))
    except Exception as e:
        print(f"[db] ensure columns failed: {e}", flush=True)
