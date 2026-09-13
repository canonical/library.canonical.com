# Database and DB Query

The application uses **PostgreSQL** via **Flask-SQLAlchemy**. The database layer is spread across three files:

| File                  | Responsibility                               |
|-----------------------|----------------------------------------------|
| `webapp/db.py`        | SQLAlchemy instance                          |
| `webapp/models.py`    | ORM model definitions                        |
| `webapp/db_query.py`  | Document fetch, parse, and upsert logic      |

PostgreSQL is optional. The DB layer is activated only when `POSTGRESQL_DB_CONNECT_STRING` is set in the environment.

---

## `webapp/db.py`

Creates the shared `SQLAlchemy` instance:

```python
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
```

Initialised against the Flask app with `db.init_app(app)` during application startup.

---

## `webapp/models.py`

### `Document`

Table name: `Documents`

| Column               | Type      | Constraints            | Description                                   |
|----------------------|-----------|------------------------|-----------------------------------------------|
| `id`                 | Integer   | Primary key            | Auto-incrementing row ID                      |
| `google_drive_id`    | String    | Unique, not null       | Google Drive file ID                          |
| `date_planned_review`| Date      | Nullable               | Planned review date parsed from doc metadata  |
| `doc_type`           | String    | Nullable               | Normalised document type                      |
| `owner`              | String    | Nullable               | Comma-separated owner names from metadata     |
| `full_html`          | Text      | Not null               | Full exported HTML from Google Drive          |
| `path`               | String    | Unique, not null, indexed | Site URL path (e.g. `/section/page`)       |
| `doc_metadata`       | JSON      | Nullable               | Raw metadata dict extracted by the parser     |
| `headings_map`       | JSON      | Nullable               | Structured heading hierarchy for ToC          |

Valid `doc_type` values: `"Introduction"`, `"How to"`, `"Reference"`, `"Entity Page"`, or `None`.

### `Analytics`

Table name: `Analytics`

| Column             | Type    | Constraints            | Description                   |
|--------------------|---------|------------------------|-------------------------------|
| `id`               | Integer | Primary key            | Auto-incrementing row ID      |
| `path`             | String  | Unique, not null, indexed | Site URL path              |
| `views`            | Integer | Nullable, default 0    | Total page views              |
| `sessions`         | Integer | Nullable, default 0    | Total sessions                |
| `engaged_sessions` | Integer | Nullable, default 0    | Engaged sessions              |

---

## Schema Initialisation (`webapp/app.py`)

Schema creation runs automatically at startup via three helpers. All are guarded by `db_can_write()` so they are skipped silently on read-only replicas.

### `db_can_write() → bool`

Executes `SHOW transaction_read_only`. Returns `True` if the database is writable.

### `ensure_documents_table()`

Creates the `Documents` table via `db.create_all()` if it does not exist.

### `ensure_documents_columns()`

Adds any missing columns to `Documents` using `ALTER TABLE … ADD COLUMN IF NOT EXISTS`:

- `doc_type VARCHAR`
- `date_planned_review DATE`
- `owner VARCHAR`
- `doc_metadata JSON`
- `headings_map JSON`

Also ensures the unique index `documents_path_uidx` on `path`.

### `ensure_analytics_table()`

Creates the `Analytics` table via `db.create_all()` if it does not exist.

---

## `webapp/db_query.py`

### Runtime DB Toggle

```python
USE_DB_ENV = "POSTGRESQL_DB_CONNECT_STRING" in os.environ
_USE_DB_RUNTIME = True  # set to False at runtime on certain errors
```

`use_db() → bool` returns `True` only when both flags are `True`.

If an `OperationalError` or `ProgrammingError` is encountered (e.g. table missing, connection lost), `_disable_db(reason)` sets `_USE_DB_RUNTIME = False` and logs the reason. This prevents repeated failed DB calls for the lifetime of the process.

---

### `_normalize_doc_type(t) → str | None`

Normalises a raw type string from document metadata to one of the canonical values:

| Input variants          | Normalised output |
|-------------------------|-------------------|
| `"how to"`, `"how-to"`  | `"How to"`        |
| `"introduction"`        | `"Introduction"`  |
| `"reference"`           | `"Reference"`     |
| `"entity page"`, `"entity"` | `"Entity Page"` |
| Anything else           | `None`            |

---

### `get_or_parse_document(google_drive, doc_id, doc_dict, doc_name)`

Returns a `Parser` instance for the given document, using the DB as a cache.

**Logic:**

1. If `use_db()` is `True`, query `Documents` by `google_drive_id`.
   - On a hit, construct a `Parser` from the stored `full_html`, `doc_metadata`, and `headings_map` (no Drive API call).
   - On `OperationalError` / `ProgrammingError`, disable DB and fall through.
2. If not found or DB unavailable, call `Parser(google_drive, doc_id, doc_dict, doc_name)` to fetch from Drive and parse.
3. If `use_db()` is still `True` after parsing, save the result to the DB:
   - Extracts `owner`, `doc_type`, `date_planned_review`, and `path` from the parser metadata.
   - Inserts a new `Document` row.
   - On `IntegrityError` (duplicate `path`), updates the existing row for that path.
4. After saving, calls `opensearch_index_document` to sync the document to OpenSearch (errors are caught and logged, not re-raised).

---

### `parse_and_upsert_document(google_drive, doc_id, doc_dict, doc_name) → tuple[str, str]`

Force-parses a document from Google Drive (bypasses the DB read cache) and upserts it into PostgreSQL.

Returns `(status, path)` where `status` is `"created"` or `"updated"`.

Used by the `update_db_all_documents` scheduled job to keep all DB rows current.

---

## Environment Variables

| Variable                      | Description                                       |
|-------------------------------|---------------------------------------------------|
| `POSTGRESQL_DB_CONNECT_STRING`| SQLAlchemy connection string for PostgreSQL       |

---

## Data Flow Summary

```
HTTP request
    │
    ▼
get_or_parse_document()
    │
    ├─ DB hit ──► Parser (from stored HTML) ──► return
    │
    └─ DB miss ──► GoogleDrive.fetch_document()
                       │
                       ▼
                   Parser (parse HTML)
                       │
                       ├─► Save to Documents table
                       │       │
                       │       └─► opensearch_index_document()
                       │
                       └─► return Parser
```
