import os
import sys
import psycopg2

DATABASE_URI = os.environ["POSTGRESQL_DB_CONNECT_STRING"]

CREATE_DOCUMENTS_SQL = """
CREATE TABLE "Documents" (
    id SERIAL PRIMARY KEY,
    google_drive_id VARCHAR NOT NULL UNIQUE,
    date_planned_review DATE NULL,
    doc_type VARCHAR NULL,
    owner VARCHAR NULL,
    full_html TEXT NOT NULL,
    path VARCHAR NOT NULL UNIQUE,
    doc_metadata JSON NULL,
    headings_map JSON NULL
);
"""

def is_read_only(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute("SHOW transaction_read_only;")
        val = (cur.fetchone() or ["on"])[0]
        return str(val).lower() in ("on", "true", "1")

def drop_and_recreate_documents(conn):
    with conn.cursor() as cur:
        cur.execute('DROP TABLE IF EXISTS "Documents" CASCADE;')
        cur.execute(CREATE_DOCUMENTS_SQL)

def migrate():
    with psycopg2.connect(DATABASE_URI) as conn:
        if is_read_only(conn):
            print("ERROR: DB is read-only; cannot run DDL. Use a RW endpoint.", file=sys.stderr)
            sys.exit(1)
        drop_and_recreate_documents(conn)
        conn.commit()
        print('Dropped and recreated table "Documents".')

if __name__ == "__main__":
    migrate()