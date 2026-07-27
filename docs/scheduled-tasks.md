# Scheduled Tasks

Scheduled tasks are managed by **APScheduler** (`BackgroundScheduler`). The scheduler is started once inside `init_scheduler(app)`, which is called from the `@app.before_request` hook on the first incoming request.

---

## Scheduler Initialization

`init_scheduler(app)` registers all jobs and starts the scheduler. It returns the `BackgroundScheduler` instance.

All inner task functions are closures that have access to the `app` object and global state variables (`nav_changes`, `cache_warming_in_progress`, etc.).

---

## Jobs

### `scheduled_task` — Every 5 minutes

Polls Google Drive for recent file changes and delegates to `process_changes`.

- Calls `google_drive.get_latest_changes()` to fetch changes from the last 5 minutes.
- Calls `process_changes(changes, navigation, google_drive)` to detect path renames.
- When a document path changes, `GoggleSheet.update_urls()` is called to update the redirect spreadsheet, and `url_updated` is set to `True`.
- Also runs **once immediately** on scheduler start.

### `update_db_all_documents` — On start + every Sunday at 06:30

Re-parses every document in Google Drive and upserts the result into PostgreSQL.

- Builds the navigation tree to get a full `doc_reference_dict`.
- Uses a `ThreadPoolExecutor` (workers controlled by `INGEST_WORKERS` env var, default `10`).
- For each document calls `parse_and_upsert_document`, then invalidates the corresponding Redis view-cache key.
- Reports `updated`, `created`, and `errors` counts to stdout.
- Also runs **once immediately** on scheduler start.

### `check_status_cache` — 5 minutes after start + every Sunday at 07:00

Warms the Redis cache for all known URLs.

- **Skipped silently** if static assets (`static/css/styles.css`, hashed CSS bundle) are not yet present on disk.
- Deletes the old `url_list.txt` if it exists.
- Calls `construct_navigation_data()` to refresh the navigation cache.
- Calls `get_urls_expiring_soon()` to collect all URLs from `url_list.txt`.
- Calls `warm_cache_for_urls(urls)` to pre-render and cache each URL.

> **Initial delay:** The first run is scheduled 5 minutes after startup via a `"date"` trigger to allow static assets to be built before cache warming begins.

### `sync_open_search` — On start + every Sunday at 07:30

Runs `opensearch_sync_all()` to perform a full reindex of all PostgreSQL `Document` rows into OpenSearch.

- Upserts every document via the `_bulk` API.
- Removes orphaned OpenSearch documents not present in the DB (`delete_orphans=True`).
- For large datasets (>10 000 documents), writes to a temporary index and performs an alias swap.

### `weekly_comment_notifications` — Every Monday at 09:00

Checks documents modified in the last week for unresolved Google Docs comments and sends notification emails to the document owners.

- Requires `SMTP_USER` and `SMTP_PASSWORD` environment variables; skips if either is missing.
- Fetches the list of recently modified docs from Google Drive.
- Resolves owner names via `owner_registry.lookup`.
- Delegates email sending to `NotificationService.send_weekly_comment_notifications`.

### `ingest_all_documents_job` — Every 6 hours

Ensures every document in Google Drive has a corresponding row in PostgreSQL. Only creates missing rows; does not update existing ones.

- Requires `POSTGRESQL_DB_CONNECT_STRING`.
- Uses a `ThreadPoolExecutor` (workers from `INGEST_WORKERS`, default `10`).
- Each worker creates its own `GoogleDrive` instance (httplib2 is not thread-safe).
- Reports `created`, `skipped`, and `errors` counts.

### `monthly_analytics_import` — 2nd of each month at 02:00

Imports page analytics from a Google Sheet into the PostgreSQL `Analytics` table.

- Requires `POSTGRESQL_DB_CONNECT_STRING` and `ANALYTICS_SHEET_ID`.
- Sheet is identified by `ANALYTICS_SHEET_ID`; tab by `ANALYTICS_SHEET_TAB` (default `Sheet1`); first data row by `ANALYTICS_START_ROW` (default `16`).
- Upserts records keyed by `path`. Reports `created`, `updated`, and `errors`.

### `monthly_analytics_sync_opensearch` — 2nd of each month at 03:00

Syncs the `Analytics` PostgreSQL table to the `library-analytics` OpenSearch index.

- Runs one hour after `monthly_analytics_import` to ensure analytics data is available.
- Creates the index with proper mappings if it does not exist.
- Uploads all rows via the `_bulk` API.

---

## Schedule Summary

| Job                               | Trigger                                      |
|-----------------------------------|----------------------------------------------|
| `scheduled_task`                  | On start, then every 5 minutes              |
| `update_db_all_documents`         | On start, then every Sunday at 06:30        |
| `check_status_cache`              | 5 min after start, then every Sunday at 07:00 |
| `sync_open_search`                | On start, then every Sunday at 07:30        |
| `weekly_comment_notifications`    | Every Monday at 09:00                       |
| `ingest_all_documents_job`        | Every 6 hours                               |
| `monthly_analytics_import`        | 2nd of each month at 02:00                  |
| `monthly_analytics_sync_opensearch` | 2nd of each month at 03:00               |

---

## Environment Variables

| Variable              | Default        | Used by                                      |
|-----------------------|----------------|----------------------------------------------|
| `INGEST_WORKERS`      | `10`           | `ingest_all_documents_job`, `update_db_all_documents` |
| `ANALYTICS_SHEET_ID`  | *(required)*   | `monthly_analytics_import`                   |
| `ANALYTICS_SHEET_TAB` | `Sheet1`       | `monthly_analytics_import`                   |
| `ANALYTICS_START_ROW` | `16`           | `monthly_analytics_import`                   |
| `SMTP_USER`           | *(required)*   | `weekly_comment_notifications`               |
| `SMTP_PASSWORD`       | *(required)*   | `weekly_comment_notifications`               |
| `OPENSEARCH_URL`      | *(required)*   | `sync_open_search`, `monthly_analytics_sync_opensearch` |
| `OPENSEARCH_USERNAME` | *(required)*   | Same as above                                |
| `OPENSEARCH_PASSWORD` | *(required)*   | Same as above                                |
| `OPENSEARCH_INDEX`    | `library-docs` | `sync_open_search`                           |
