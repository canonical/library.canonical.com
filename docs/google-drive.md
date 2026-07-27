# Google Drive

Google Drive integration is implemented in `webapp/googledrive.py` via the `GoogleDrive` class. It wraps the Google Drive v3 and Google Docs v1 APIs using a service account.

---

## Authentication

The `GoogleDrive` class authenticates using a service account. Credentials are loaded from `SERVICE_ACCOUNT_INFO` (defined in `webapp/settings.py`).

The required OAuth scope is `https://www.googleapis.com/auth/drive`.

An `AuthorizedHttp` adapter wraps `httplib2.Http` with a 30-second timeout, and the Drive v3 service client is built with `cache_discovery=False`.

---

## Class: `GoogleDrive`

### `__init__(cache)`

Initialises the Drive v3 service client and stores the Flask-Caching `cache` instance for use by other methods.

---

### `search_drive(query) → list`

Performs a full-text and name search within the shared drive.

Drive API query:
```
(name contains '<query>' or fullText contains '<query>') and trashed = false
```

Returns a list of file objects with fields: `id`, `name`, `mimeType`, `description`.

On API error, aborts with HTTP 500.

---

### `get_document_list() → list`

Returns the complete list of files in the shared drive, handling pagination via `nextPageToken`.

Fields fetched per file: `id`, `name`, `mimeType`, `parents`, `owners`, `modifiedTime`.

- The URL spreadsheet file (identified by `URL_FILE`) is excluded from the list.
- Results are cached under the key `"docDic"`.
- On API failure, falls back to the cached `"docDic"` if available; otherwise aborts with HTTP 503.

---

### `get_changes() → list`

Fetches the complete change log for the shared drive since the current page token.

Returns all change objects including removed items (`includeRemoved=True`, `includeCorpusRemovals=True`).

On error, aborts with HTTP 500.

---

### `get_latest_changes() → list`

Fetches only recent changes (last 5 minutes) using an incrementally advancing page token.

- The page token is persisted in the cache under `"startPageToken"`.
- On the first call (no cached token), the current start token is fetched from the API.
- After processing all pages, the last usable token is stored back in the cache.
- Changes are filtered to those with a `time` field within the last 5 minutes.

Returns a list of recent change objects.

---

### `fetch_document(document_id) → str`

Exports a Google Doc as HTML using the Drive v3 export API (`mimeType="text/html"`).

- Downloads the file in chunks via `MediaIoBaseDownload`.
- Returns the HTML string on success.
- On `exportSizeLimitExceeded` error, falls back to `_fetch_document_via_docs_api`.
- On `fileNotExportable` or `internalError`, raises `ValueError`.
- On 404, aborts with HTTP 404; on other errors, aborts with HTTP 500.

---

### `_fetch_document_via_docs_api(document_id) → str`

Fallback for documents that exceed the Drive export size limit.

- Builds a separate Google Docs v1 service client.
- Fetches the document JSON and converts it to HTML via `_docs_api_to_html`.

---

### `_docs_api_to_html(document) → str`

Converts a Google Docs API JSON response to a minimal HTML string.

Supported elements:

| Docs element  | HTML output                          |
|---------------|--------------------------------------|
| `HEADING_1–6` | `<h1>–<h6>`                          |
| `NORMAL_TEXT` | `<p>`                                |
| Bold text run | `<strong>`                           |
| Italic text run | `<em>`                             |
| Underline text run | `<u>`                          |

---

### `fetch_spreadsheet(document_id) → str`

Exports a Google Sheet as CSV using the Drive v3 export API (`mimeType="text/csv"`). Returns the raw CSV string.

On error, aborts with HTTP 500.

---

### `create_copy_template(name) → str | None`

Creates a copy of the default template document (identified by `DEFAULT_DOC` env var) in the drafts folder (`DRAFT_FOLDER`).

- Sets the copy's name to `"Draft: <name>"`.
- Moves the copy to the drafts folder.
- Returns the new file's ID on success, or `None` on error.

---

### `get_changes_last_week() → list`

Returns a list of Google Doc files (non-folder, non-trashed) modified in the last 7 days within the shared drive.

Drive API query:
```
mimeType = 'application/vnd.google-apps.document'
and trashed = false
and modifiedTime > '<one week ago>'
```

Returns file objects with fields: `id`, `name`, `modifiedTime`.

---

### `get_unresolved_comments_count(document_id) → int`

Returns the number of unresolved (open) comments on a given document.

Uses the Drive v3 comments API with `fields="comments(resolved)"` and `includeDeleted=False`.

Returns `0` on error.

---

## Environment Variables

| Variable       | Default                                        | Description                              |
|----------------|------------------------------------------------|------------------------------------------|
| `TARGET_DRIVE` | `0ABG0Z5eOlOvhUk9PVA`                         | Shared Drive ID                          |
| `URL_FILE`     | `16mTPcMn9hxjgra62ArjL6sTg75iKiqsdN99vtmrlyLg` | Google Sheet ID for URL redirects       |
| `DEFAULT_DOC`  | `1YxnWy94YrNnraf1OAxXfIAbL677nNjvb-AWp1TaxU9s` | Template document ID                    |
| `DRAFT_FOLDER` | `1cI2ClDWDzv3osp0Adn0w3Y7zJJ5h08ua`           | Google Drive folder ID for draft copies |

---

## Caching

| Cache key       | Contents                                          |
|-----------------|---------------------------------------------------|
| `"docDic"`      | Dict of `{file_id: file_object}` for all Drive files |
| `"startPageToken"` | Last used change page token for incremental polling |
