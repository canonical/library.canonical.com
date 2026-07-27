# Routes

All HTTP routes are defined in `webapp/app.py` using the `FlaskBase` application instance.

---

## General / Document Routes

### `GET /`  
### `GET /<path:path>`

The main document renderer. Serves every page of the library site.

- Looks up the navigation hierarchy to find the target document.
- Fetches and parses the Google Docs HTML via `get_or_parse_document`.
- Renders `index.html` with navigation, document content, and metadata.
- Responses are cached in Redis (TTL 7 days) unless Redis is unhealthy or static assets are not ready yet.
- On an unknown path, attempts a redirect lookup from the URL redirect list before returning a 404.

---

## Navigation / Cache Routes

### `GET /refresh-navigation`

Clears the navigation cache entry and the root view cache, then redirects to `/`. Forces the next request to rebuild the navigation tree from Google Drive.

### `GET /clear-cache/`  
### `GET /clear-cache/<path:path>`

Clears the cached view for a specific document path and removes the corresponding PostgreSQL row so the document is re-fetched from Google Drive on the next visit.

### `GET /clear-all-views`

Clears the root view cache, the navigation cache, and every per-document view cache entry listed in `static/assets/url_list.txt`. Useful after a new CSS bundle is deployed.

### `GET /restore-cleared-cached`

Reads all URLs from `static/assets/url_list.txt` and warms the cache for each one in a background thread. Redirects immediately to `/`.

---

## URL / Redirect Routes

### `GET /update-urls-doc`

Manually triggers `scheduled_get_changes()` to detect document moves in Google Drive and update the redirect spreadsheet, then redirects to `/`.

### `GET /update-url-list`

Re-fetches the URL redirect list from the Google Spreadsheet identified by `URL_FILE` env var. Redirects to `/` on completion.

---

## Search Route

### `GET /search`

Full-text search endpoint. See [search.md](search.md) for details.

Query parameters:

| Parameter  | Default          | Description                               |
|------------|------------------|-------------------------------------------|
| `q`        | *(empty)*        | Search query string                       |
| `size`     | `20`             | Maximum number of results to return       |
| `index`    | `library-docs`   | OpenSearch index to query                 |
| `operator` | `or`             | Boolean operator for multi-term queries   |

---

## Changes Route

### `GET /changes`

Fetches and displays all changes from Google Drive since the last page token. Renders `changes.html`.

---

## Template / Utility Routes

### `GET /create-copy-template`

Creates a personal copy of the library document template for the authenticated user. Redirects to the new Google Doc (or to the drafts folder on failure).

### `GET /test-500`

Renders the 500 error page with a dummy message for UI preview purposes.

### `GET /sentry-test`

Deliberately raises a `ZeroDivisionError` to test Sentry error reporting.

---

## Health Check

### `GET /_status/health`

Returns application health status as JSON.

Response fields:

| Field     | Description                                          |
|-----------|------------------------------------------------------|
| `status`  | `"ok"` or `"error"`                                  |
| `uptime`  | Seconds since the application started               |
| `timestamp` | UTC timestamp of the check                        |
| `pg`      | PostgreSQL status: `"ok"`, `"error"`, or `"not_configured"` |
| `checks`  | Detailed check results (pg latency, db timestamp)   |

Returns HTTP 200 on success, 503 on error.

---

## Analytics Routes

### `GET /analytics/upload`  
### `POST /analytics/upload`

Reads page analytics data from the Google Sheet configured by:

- `ANALYTICS_SHEET_ID` — sheet identifier (required)
- `ANALYTICS_SHEET_TAB` — tab name (default: `Sheet1`)
- `ANALYTICS_START_ROW` — first data row (default: `16`)

Upserts `path`, `views`, `sessions`, and `engaged_sessions` into the `Analytics` PostgreSQL table. Returns a JSON summary.

### `GET /analytics/opensearch/upload`  
### `POST /analytics/opensearch/upload`

Uploads all rows from the `Analytics` PostgreSQL table to the `library-analytics` OpenSearch index. Creates the index with proper mappings if it does not exist. Returns a JSON bulk-operation summary.

---

## Notification Routes

### `GET /notifications/weekly-comments`  
### `POST /notifications/weekly-comments`

Checks all documents modified in the last week for unresolved comments, resolves owner email addresses, and sends notification emails. Returns a JSON summary with email counts.

### `GET /notifications/weekly-comments-view`

Renders `weekly_notifications.html` showing documents with unresolved comments grouped by owner. Statistics (total modified, total comments, docs without owner) are included in the template context.

---

## Validation Route

### `GET /validate-links`

Manually triggers the link-validation job (`validate_and_report`) against the URL set in `BASE_URL` (default `http://localhost:8051`). Returns JSON `{"status": "success"}` or `{"status": "error", "message": "..."}`.

---

## OpenSearch Admin Routes

### `GET /opensearch/bulk/run`  
### `POST /opensearch/bulk/run`

Streams all `Document` rows from PostgreSQL to OpenSearch via the `_bulk` API. Requires `OPENSEARCH_URL`, `OPENSEARCH_USERNAME`, and `OPENSEARCH_PASSWORD`.

Query parameters:

| Parameter | Default        | Description                    |
|-----------|----------------|--------------------------------|
| `index`   | `library-docs` | Target OpenSearch index name   |

### `GET /opensearch/indices`

Proxies `GET /_cat/indices?format=json` to OpenSearch and returns the raw response.

### `GET /opensearch/docs`

Lists documents from an OpenSearch index.

Query parameters:

| Parameter | Default        | Description                         |
|-----------|----------------|-------------------------------------|
| `index`   | `library-docs` | Index to query                      |
| `q`       | *(none)*       | Optional query string               |
| `size`    | `50`           | Page size                           |
| `from`    | `0`            | Pagination offset                   |
| `raw`     | `0`            | Set to `1` to return raw OS response |

---

## Error Pages

| Template     | Rendered when                              |
|--------------|--------------------------------------------|
| `404.html`   | Path not found and no redirect exists      |
| `500.html`   | Document parsing fails or an exception occurs |
