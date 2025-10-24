# =========================
# Imports and Environment
# =========================
import os
import copy
import flask
from apscheduler.schedulers.background import BackgroundScheduler
import dotenv
import json
import ssl
import base64
import binascii
import textwrap
import requests
from flask import jsonify, request, g, session, has_request_context
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect, text
from requests.adapters import HTTPAdapter

# import talisker
from canonicalwebteam.flask_base.app import FlaskBase
from concurrent.futures import ThreadPoolExecutor
from threading import Thread

from webapp.db_query import get_or_parse_document
from webapp.googledrive import GoogleDrive
from webapp.navigation_builder import NavigationBuilder
from webapp.sso import init_sso
from webapp.spreadsheet import GoggleSheet
from flask_caching import Cache
from webapp.db import db
from webapp.utils.make_snippet import render_snippet
from webapp.models import Document

for key, value in os.environ.items():
    if key.startswith("FLASK_"):
        # Set environment variable without the 'FLASK_' prefix
        os.environ[key[6:]] = value

dotenv.load_dotenv(".env")
dotenv.load_dotenv(".env.local", override=True)

print("REDIS_DB_CONNECT_STRING:", os.getenv("REDIS_DB_CONNECT_STRING"))

ROOT = os.getenv("ROOT_FOLDER", "library")
TARGET_DRIVE = os.getenv("TARGET_DRIVE", "0ABG0Z5eOlOvhUk9PVA")
URL_DOC = os.getenv("URL_FILE", "16mTPcMn9hxjgra62ArjL6sTg75iKiqsdN99vtmrlyLg")
DRAFTS_URL = (
    "https://drive.google.com/drive/folders/1cI2ClDWDzv3osp0Adn0w3Y7zJJ5h08ua"
)

# =========================
# App and Extension Initialization
# =========================
app = FlaskBase(
    __name__,
    "library.canonical.com",
    template_folder="../templates",
    template_404="404.html",
    template_500="500.html",
    static_folder="../static",
)
# Initialize the App SSO
init_sso(app)

# Initialize the connection to DB
def db_can_write() -> bool:
    try:
        with db.engine.connect() as conn:
            ro = conn.execute(text("SHOW transaction_read_only")).scalar()
            return str(ro).lower() in ("off", "false", "0")
    except Exception as e:
        print(f"[db] read-only probe failed: {e}", flush=True)
        return False

def ensure_documents_table():
    """
    Create schema once if missing and DB is writable.
    Skip silently on read-only endpoints.
    """
    try:
        with app.app_context():
            insp = inspect(db.engine)
            if "Documents" in insp.get_table_names():
                return
            if db_can_write():
                print("[db] Creating schema via create_all()", flush=True)
                db.create_all()
            else:
                print("[db] Documents table missing but DB is read-only; skipping create_all()", flush=True)
    except Exception as e:
        print(f"[db] ensure schema failed: {e}", flush=True)



if "POSTGRESQL_DB_CONNECT_STRING" in os.environ:
    print("\n\nUsing PostgreSQL database\n\n", flush=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "POSTGRESQL_DB_CONNECT_STRING"
    )
    db.init_app(app)
    ensure_documents_table()
    # Only for Local testing
    # with app.app_context():
    #     db.create_all()

# Initialize the connection to Redis or SimpleCache
if "REDIS_DB_CONNECT_STRING" in os.environ:

    cache = Cache(
        app,
        config={
            "CACHE_TYPE": "RedisCache",
            "CACHE_REDIS_URL": os.getenv(
                "REDIS_DB_CONNECT_STRING", "redis://localhost:6379"
            ),  # default Redis DB # optional, overrides host/port/db
        },
    )
    print("\n\nUsing Redis cache\n\n", flush=True)
else:
    cache = Cache(app, config={"CACHE_TYPE": "simple"})

cache.init_app(app)

# =========================
# Global State Variables
# =========================
nav_changes = None
url_updated = False
gdrive_instance = None
initialized_executed = False
cache_warming_in_progress = False
cache_navigation_data = None
cache_updated = False


# =========================
# Utility Functions
# =========================
def get_google_drive_instance():
    """
    Return a singleton instance of GoogleDrive and cache in Flask's 'g'
    object.
    """
    if "google_drive" not in g:
        g.google_drive = GoogleDrive(cache)
    return g.google_drive


def get_list_of_urls():
    """
    Return a list of urls from Google Drive and cache in Flask's 'g'
    object.
    """

    google_drive = get_google_drive_instance()
    urls = []
    print("FETCHING SPREADSHEET", flush=True)
    print("URL_DOC", URL_DOC, flush=True)
    list = google_drive.fetch_spreadsheet(URL_DOC)
    lines = list.split("\n")[1:]
    for line in lines:
        url = line.split(",")
        urls.append({"old": url[0], "new": url[1].replace("\r", "")})
    g.list_of_urls = urls


def find_broken_url(url):
    """
    Find the new url for a given old url
    """
    if "list_of_urls" not in g:
        get_list_of_urls()
    for u in g.list_of_urls:
        if u["old"] == url:
            return u["new"]
    return None


def reset_navigation_flags(navigation):
    """
    Reset the navigation flags for the given navigation structure.
    Mostly used to reset the 'active' and 'expanded' flags when
    all documents have been cached in the background to ensure
    the navigation is in a clean state.
    """
    for key, item in navigation.items():
        item["active"] = False
        item["expanded"] = False
        if "children" in item and isinstance(item["children"], dict):
            reset_navigation_flags(item["children"])


def warm_single_url(url, navigation_data):
    """
    Warm up the cache for a single URL by simulating a request context.
    """
    try:
        path = url.lstrip("/")
        nav_copy = copy.deepcopy(navigation_data)
        print(f"Warming cache for {url} with path {path}")
        with app.test_request_context(f"/{path}"):
            g.navigation_data = nav_copy
            document(path)
    except Exception as e:
        print(f"Error warming cache for {url}: {e}")


def warm_cache_for_urls(urls):
    global cache_navigation_data
    """
    Warm up the cache for a list of URLs by using a thread pool to
    handle multiple URLs concurrently.
    """
    with app.app_context():
        navigation_data = construct_navigation_data()
        cache_navigation_data = navigation_data
        with ThreadPoolExecutor(
            max_workers=8
        ) as executor:  # Adjust workers as needed
            executor.map(
                lambda url: warm_single_url(url, navigation_data), urls
            )
        print(f"\n\n Finished cache warming for {len(urls)} URLs. \n\n")


def get_urls_expiring_soon():
    """
    Returns a list of URLs from url_list.txt whose cache
    will expire in the next hour.
    Only works if Redis is used as the cache backend.
    """
    expiring_urls = []
    url_file_path = os.path.join(app.static_folder, "assets", "url_list.txt")
    if not os.path.exists(url_file_path):
        print("URL list file not found.")
        return expiring_urls

    # Read all URLs from the file
    with open(url_file_path, "r") as f:
        urls = [line.strip() for line in f if line.strip()]

    # Check each cache key's TTL
    if "REDIS_DB_CONNECT_STRING" in os.environ:
        for url in urls:
            expiring_urls.append({"url": url})
    else:
        print("TTL checking is only supported with Redis cache.")

    return expiring_urls


def _requests_session_with_env_ca(raw):
    """
    Accepts OPENSEARCH_TLS_CA as:
      - Inline PEM chain in one line with literal '\n'
      - Regular PEM (multi-line)
      - Base64 of PEM/DER
    Returns a requests.Session with SSLContext using this CA.
    """
    if not raw:
        return None

    val = str(raw).strip().strip('"').strip("'")
    if "\\n" in val:
        val = val.replace("\\n", "\n")
    val = val.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.lstrip() for ln in val.splitlines()]
    val = "\n".join(lines).strip()

    cadata = None  # str or bytes
    if "BEGIN CERTIFICATE" in val:
        # Ensure proper formatting and trailing newline
        pem = textwrap.dedent(val).strip()
        if not pem.endswith("\n"):
            pem += "\n"
        cadata = pem
    else:
        # Try base64 decode (PEM text or DER)
        try:
            raw_bytes = base64.b64decode(val, validate=True)
        except binascii.Error:
            raise ValueError("OPENSEARCH_TLS_CA is neither PEM nor base64")
        try:
            txt = raw_bytes.decode("utf-8")
            cadata = txt if "BEGIN CERTIFICATE" in txt else raw_bytes
        except UnicodeDecodeError:
            cadata = raw_bytes

    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cadata=cadata)

    class SSLContextAdapter(HTTPAdapter):
        def __init__(self, ssl_context=None, **kwargs):
            self.ssl_context = ssl_context
            super().__init__(**kwargs)

        def init_poolmanager(self, *args, **kwargs):
            kwargs["ssl_context"] = self.ssl_context
            return super().init_poolmanager(*args, **kwargs)

        def proxy_manager_for(self, *args, **kwargs):
            kwargs["ssl_context"] = self.ssl_context
            return super().proxy_manager_for(*args, **kwargs)

    s = requests.Session()
    s.mount("https://", SSLContextAdapter(ctx))
    return s


def _ensure_highlight_limit(index_name: str, limit: int = 5_000_000) -> None:
    base_url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    tls_ca = os.getenv("OPENSEARCH_TLS_CA")
    if not (base_url and username and password):
        return
    http = _requests_session_with_env_ca(tls_ca) if tls_ca else requests
    try:
        http.put(
            f"{base_url.rstrip('/')}/{index_name}/_settings",
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            json={"index.highlight.max_analyzed_offset": limit},
            timeout=20,
        )
    except Exception as e:
        print(f"[search] failed to set max_analyzed_offset: {e}", flush=True)


# =========================
# Navigation and Document Functions
# =========================
def get_navigation_data():
    """
    Return the navigation data that was cached
    in case it is available, otherwise construct it.
    """

    if "navigation_data" not in g:

        if "navigation_data_cached" not in session:
            g.navigation_data = construct_navigation_data()
        else:
            nav_data = cache.get("navigation")
            if nav_data is None:
                # Handle the case where the cache data is missing
                g.navigation_data = construct_navigation_data()
            else:
                google_drive = get_google_drive_instance()
                g.navigation_data = NavigationBuilder(
                    google_drive,
                    ROOT,
                    True,
                    nav_data["doc_reference_dict"],
                    nav_data["temp_hierarchy"],
                    nav_data["file_list"],
                    nav_data["hierarchy"],
                )
    return g.navigation_data


def construct_navigation_data():
    """
    Construct the navigation data  using the NavigationBuilder and cache it.
    """
    google_drive = get_google_drive_instance()
    data = NavigationBuilder(google_drive, ROOT)
    nav_data = {
        "doc_reference_dict": data.doc_reference_dict,
        "temp_hierarchy": data.temp_hierarchy,
        "file_list": data.file_list,
        "hierarchy": data.hierarchy,
    }
    cache.set("navigation", nav_data)
    if has_request_context():
        session["navigation_data_cached"] = True
    return data


def get_target_document(path, navigation):
    """
    Helper function that traverses the navigation hierarchy based on the URL
    path and returns the target document.
    """
    if not path:
        navigation["index"]["active"] = True
        return navigation["index"]

    split_slug = path.split("/")
    target_page = navigation
    for index, slug in enumerate(split_slug):
        if len(split_slug) == index + 1:
            target_page[slug]["active"] = True
            if target_page[slug]["mimeType"] == "folder":
                target_page[slug]["expanded"] = True
                return target_page[slug]["children"]["index"]
            else:
                return target_page[slug]
        target_page[slug]["expanded"] = True
        target_page = target_page[slug]["children"]

    raise ValueError(f"Document for path '{path}' not found.")


# =========================
# Scheduled Tasks / Cron Jobs
# =========================
def scheduled_get_changes():
    """
    Scheduled task to get changes in document
    name or location from Google Drive.
    Then process those changes to update
    the navigation data and the urls for redirects.
    """
    global nav_changes
    google_drive = gdrive_instance
    changes = google_drive.get_latest_changes()
    nav_changes = process_changes(changes, nav_changes, gdrive_instance)


def process_changes(changes, navigation_data, google_drive):
    global url_updated
    """
    Process the list of changes for docs and
    locations from Google Drive. If a document's location
    has changed, update the URLs in the redirects file.
    """
    new_nav = NavigationBuilder(google_drive, ROOT)
    for change in changes:
        if change["removed"]:
            print("REMOVED")
        else:
            if "fileId" in change:
                if change["fileId"] in navigation_data.doc_reference_dict:
                    nav_item = navigation_data.doc_reference_dict[
                        change["fileId"]
                    ]
                    new_nav_item = new_nav.doc_reference_dict[change["fileId"]]
                    if nav_item["full_path"] != new_nav_item["full_path"]:
                        # Location Change process
                        old_path = nav_item["full_path"][1:]
                        new_path = new_nav_item["full_path"][1:]
                        GoggleSheet(old_path, new_path).update_urls()
                        url_updated = True
    return new_nav


def init_scheduler(app):
    """
    Initialize the background scheduler
    for periodic tasks.
    """

    def scheduled_task():
        """
        The task of checking for changes in
        Google Drive should be run periodically
        on a schedule, every 5 minutes.
        """
        global nav_changes
        with app.app_context():
            google_drive = gdrive_instance
            navigation = nav_changes
            changes = google_drive.get_latest_changes()
            new_nav = process_changes(changes, navigation, google_drive)
            nav_changes = new_nav

    def check_status_cache():
        """
        Check the status of the cache and warm it if needed.
        """
        global cache_warming_in_progress
        global cache_updated
        # Delete the old url_list.txt if it exists
        url_list_path = os.path.join(
            app.static_folder, "assets", "url_list.txt"
        )
        if os.path.exists(url_list_path):
            os.remove(url_list_path)
            print(f"Deleted old {url_list_path}")

        with app.app_context():
            construct_navigation_data()
        if not cache_warming_in_progress:
            print("\n\nChecking cache status...\n\n")
            expiring_urls = get_urls_expiring_soon()
            if expiring_urls:
                print(
                    f"Found {len(expiring_urls)} URLs expiring, warming cache"
                )
                cache_warming_in_progress = True
                urls_to_warm = [u["url"] for u in expiring_urls]
                warm_cache_for_urls(urls_to_warm)
                cache_warming_in_progress = False
                cache_updated = True
            else:
                print("No URLs expiring soon, no action taken.")

    def ingest_all_documents_job():
        """
        Ensure all documents exist in the DB by fetching from Drive if missing.
        Runs in parallel with a configurable number of threads.
        """
        if "POSTGRESQL_DB_CONNECT_STRING" not in os.environ:
            print("DB not configured; skipping ingest job", flush=True)
            return

        workers = int(os.getenv("INGEST_WORKERS", "10"))  # tune as needed

        with app.app_context():
            try:
                try:
                    nav = construct_navigation_data()
                except Exception:
                    nav = get_navigation_data()

                doc_dict = getattr(nav, "doc_reference_dict", {}) or {}
                items = list(doc_dict.items())
                total = len(items)
                if total == 0:
                    print("[ingest] nothing to ingest", flush=True)
                    return

                created = 0
                skipped = 0
                errors = 0

                def _ingest_one(args):
                    doc_id, meta = args
                    # New app context per thread
                    with app.app_context():
                        try:
                            # Build a fresh Drive client for this thread
                            drive = GoogleDrive(cache)
                            from webapp.models import Document

                            # Fast skip if exists
                            if (
                                db.session.query(Document.id)
                                .filter_by(google_drive_id=doc_id)
                                .first()
                            ):
                                return "skipped", doc_id, None

                            # Parse and persist
                            get_or_parse_document(
                                drive,
                                doc_id,
                                doc_dict,
                                meta.get("name", ""),
                            )
                            return "created", doc_id, None
                        except IntegrityError:
                            db.session.rollback()
                            return "skipped", doc_id, None
                        except Exception as e:
                            db.session.rollback()
                            return "error", doc_id, str(e)
                        finally:
                            # Ensure thread-local session is released
                            db.session.remove()

                print(
                    f"[ingest] starting {total} docs with {workers} workers",
                    flush=True,
                )
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    for status, doc_id, err in ex.map(_ingest_one, items):
                        if status == "created":
                            created += 1
                        elif status == "skipped":
                            skipped += 1
                        else:
                            errors += 1
                            print(
                                f"[ingest] error id={doc_id}: {err}",
                                flush=True,
                            )
                content = f"done created={created} skipped={skipped} "
                content_2 = f"errors={errors} total={total}"
                print(
                    f"[ingest] {content} {content_2}",
                    flush=True,
                )
            except Exception as e:
                print(f"[ingest] fatal error: {e}", flush=True)

    # Initialize the scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_task)  # Run once
    scheduler.add_job(check_status_cache)  # Run on load
    scheduler.add_job(ingest_all_documents_job)  # Run on load
    scheduler.add_job(scheduled_task, "interval", minutes=5)
    # Optionally re-run ingest every N hours (uncomment if desired)
    scheduler.add_job(ingest_all_documents_job, "interval", hours=6)
    scheduler.start()
    return scheduler


# =========================
# Route Definitions
# =========================
@app.route("/refresh-navigation")
def refresh_navigation():
    """
    Route to manually refresh the navigation data.
    """
    new_path = ""
    cache_key = "view//%s" % new_path

    print("Cache Key", cache_key)
    if cache.delete(cache_key):  # Delete the cache entry
        print(f"Cache for '{new_path}' has been cleared.", 200)
    session.pop("navigation_data_cached", None)
    cache.delete("navigation")
    return flask.redirect("/")


@app.route("/search")
def search_drive():
    """
    Search: use OpenSearch when configured; fallback to Drive
    Query params:
      - q: query string (optional)
      - size: number of results (default 50)
      - index: override index (default OPENSEARCH_INDEX or 'library-docs')
      - operator: 'or' (default) or 'and' for q queries
    """
    q = request.args.get("q", "") or ""
    size = int(request.args.get("size", "20"))
    index_name = request.args.get("index") or os.getenv(
        "OPENSEARCH_INDEX", "library-docs"
    )
    operator = (
        request.args.get("operator")
        or os.getenv("OPENSEARCH_DEFAULT_OPERATOR", "or")
    ).lower()
    operator = operator if operator in ("and", "or") else "or"

    navigation_data = get_navigation_data()

    base_url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    tls_ca = os.getenv("OPENSEARCH_TLS_CA")

    search_results = None
    used_opensearch = False

    if base_url and username and password:
        try:
            http = (
                _requests_session_with_env_ca(tls_ca) if tls_ca else requests
            )
            print(
                "Querying OpenSearch...",
                flush=True,
            )

            # Use POST with full_html and get highlights
            body = {
                "query": {
                    "query_string": {
                        "query": q if q else "*",
                        "default_operator": operator,
                    }
                },
                "_source": {
                    "includes": [
                        "path",
                        "owner",
                        "type",
                        "doc_metadata",
                        "full_html",
                    ]
                },
                "size": size,
            }
            if q:
                body["highlight"] = {
                    "type": "unified",
                    "order": "score",
                    "require_field_match": False,
                    "fields": {
                        "full_html": {
                            "type": "unified",
                            "fragment_size": 300,
                            "number_of_fragments": 1,
                            "boundary_scanner": "sentence",
                            "boundary_scanner_locale": "en-US",
                            "pre_tags": ["<strong>"],
                            "post_tags": ["</strong>"],
                        }
                    },
                }
            else:
                body["sort"] = [{"_id": "desc"}]

            resp = http.post(
                f"{base_url.rstrip('/')}/{index_name}/_search",
                auth=(username, password),
                headers={"Content-Type": "application/json"},
                json=body,
                timeout=30,
            )

            # If we hit the 400 offset error, bump setting and retry once
            if resp.status_code == 400:
                try:
                    err = resp.json()
                except Exception:
                    err = {"error": {"reason": resp.text}}
                reason_blob = json.dumps(err.get("error", {})).lower()
                if (
                    "max_analyzed_offset" in reason_blob
                    or "max analyzed offset" in reason_blob
                ):
                    print("[search] raising limit and retrying", flush=True)
                    _ensure_highlight_limit(index_name, 5_000_000)
                    resp = http.post(
                        f"{base_url.rstrip('/')}/{index_name}/_search",
                        auth=(username, password),
                        headers={"Content-Type": "application/json"},
                        json=body,
                        timeout=30,
                    )
            # Handle response
            if resp.ok:
                print("OpenSearch succeeded", flush=True)
                data = resp.json()
                print(
                    f"OpenSearch {data.get('hits', {}).get('total', {})}",
                    flush=True,
                )
                hits = data.get("hits", {}).get("hits", [])
                print(
                    f"[search] OpenSearch found {len(hits)} hits", flush=True
                )

                results = []
                for h in hits:
                    gid = h.get("_id")
                    src = h.get("_source") or {}
                    meta = src.get("doc_metadata") or {}
                    type = meta.get("type") or ""
                    # Prefer OS highlight or full_html fallback
                    hl = (h.get("highlight") or {}).get("full_html")
                    description = render_snippet(
                        hl, src.get("full_html") or "", q
                    )
                    print(type, flush=True)
                    results.append(
                        {
                            "id": gid,
                            "full_path": src.get("path") or "",
                            "breadcrumbs": src.get("path", "").split("/")[:-1],
                            "name": meta.get("title")
                            or (src.get("path") or gid),
                            "owner": src.get("owner"),
                            "type": type,
                            "description": description,
                        }
                    )
                search_results = results
                used_opensearch = True
            else:
                print(
                    f"OpenSearch failed {resp.status_code}: {resp.text[:300]}",
                    flush=True,
                )
        except Exception as e:
            print(f"[search] OpenSearch error: {e}", flush=True)

    # Fallback only if OpenSearch not configured or errored out
    if search_results is None:
        print("[search] Falling back to Google Drive search", flush=True)
        google_drive = get_google_drive_instance()
        search_results = google_drive.search_drive(q)

    return flask.render_template(
        "search.html",
        search_results=search_results,
        doc_reference_dict=navigation_data.doc_reference_dict,
        query=q,
        TARGET_DRIVE=TARGET_DRIVE,
        navigation=navigation_data.hierarchy,
        previous_slug=request.path.strip("/"),
        used_opensearch=used_opensearch,
    )


@app.route("/update-urls-doc")
def update_urls(path=None):
    """
    Route to trigger a manual update of the URLs redirects file.
    """
    scheduled_get_changes()
    new_path = path.replace("update-urls", "")
    return flask.redirect("/" + new_path)


@app.route("/update-url-list")
def update_url_list():
    """
    Manually refresh the list of URLs from Google Drive.
    """
    get_list_of_urls()
    print("\n\n URL list updated via /update-url-list \n\n")
    return flask.redirect("/")


@app.route("/changes")
def changes_drive():
    """
    Route to search the Google Drive. The search results are displayed in a
    separate page.
    """
    google_drive = get_google_drive_instance()
    changes_results = google_drive.get_changes()
    navigation_data = get_navigation_data()

    return flask.render_template(
        "changes.html",
        changes_results=changes_results,
        TARGET_DRIVE=TARGET_DRIVE,
        doc_reference_dict=navigation_data.doc_reference_dict,
    )


@app.route("/create-copy-template")
def create_copy_template():
    """
    Route to create a copy of the template document for the library.
    """
    google_drive = get_google_drive_instance()
    name = flask.session.get("openid").get("fullname")
    file_id = google_drive.create_copy_template(name)
    if file_id:
        return flask.redirect(
            "https://docs.google.com/document/d/%s/edit" % file_id
        )
    else:
        return flask.redirect(DRAFTS_URL)


@app.route("/clear-cache/")
@app.route("/clear-cache/<path:path>")
def clear_cache_doc(path=None):
    """
    Clear cache for a specific document and remove its DB row.
    so it will be refetched from Google Drive on next access.
    """
    print("Clearing cache")
    print("PATH\n", path)
    if path is None:
        new_path = ""
    else:
        # path is already relative; replace is harmless
        new_path = path.replace("/clear-cache", "")

    # Delete the DB row for this document (if DB is enabled)
    if "POSTGRESQL_DB_CONNECT_STRING" in os.environ:
        try:
            # Try to resolve the Google Drive ID from navigation
            gid = None
            try:
                navigation_data = get_navigation_data()
                target = (
                    get_target_document(new_path, navigation_data.hierarchy)
                    if new_path
                    else navigation_data.hierarchy["index"]
                )
                gid = target.get("id")
            except Exception as e:
                print(
                    f"Could not resolve target doc from navigation: {e}",
                    flush=True,
                )

            deleted = 0
            if gid:
                deleted = Document.query.filter_by(
                    google_drive_id=gid
                ).delete()
            if not deleted:
                full_path = f"/{new_path}" if new_path else "/"
                deleted = Document.query.filter_by(path=full_path).delete()

            db.session.commit()
            print(
                f"DB: deleted rows={deleted} for path '{new_path}'", flush=True
            )
        except Exception as e:
            print(f"DB delete failed for '{new_path}': {e}", flush=True)

    # Clear the view cache entry
    cache_key = "view//%s" % new_path
    print("Cache Key", cache_key)
    if cache.delete(cache_key):
        print(f"Cache for '{new_path}' has been cleared.", 200)
    else:
        print(f"Cache for '{new_path}' not found.", 404)

    print("Redirecting to", new_path)
    return flask.redirect("/" + new_path)


@app.route("/")
@app.route("/<path:path>")
@cache.cached(timeout=604800)  # 7 days cached = 604800 seconds 1 day = 86400
def document(path=None):
    global url_updated
    global cache_updated
    """
    The entire site is rendered by this function (except /search). As all
    pages use the same template, the only difference between them is the
    content.
    """

    # Handle navigation data refresh after cache warming or URL update
    if cache_updated:
        cache_updated = False
        navigation_data = construct_navigation_data()
        g.navigation_data = navigation_data
    # Handle navigation data refresh after URL update
    elif url_updated and not cache_warming_in_progress:
        url_updated = False
        navigation_data = construct_navigation_data()
        g.navigation_data = navigation_data
    # If cache warming is in progress, use a copy of the navigation data
    elif cache_warming_in_progress:
        print("Cache warming in progress, skipping navigation construction.")
        navigation_data = copy.deepcopy(cache_navigation_data)
    # Otherwise, get navigation data from cache or build if needed
    else:
        navigation_data = get_navigation_data()

    # Reset all navigation flags before marking the current document
    reset_navigation_flags(navigation_data.hierarchy)

    # Try to find and mark the target document as active/expanded
    try:
        target_document = get_target_document(path, navigation_data.hierarchy)
    except KeyError:
        # If not found, check for a redirect (broken URL mapping)
        new_path = find_broken_url(path)
        if new_path:
            path = new_path
            return flask.redirect("/" + path)
        else:
            err = "Error, document does not exist."
            flask.abort(404, description=err)

    # Parse the document content from Google Drive
    soup = get_or_parse_document(
        get_google_drive_instance(),
        target_document["id"],
        navigation_data.doc_reference_dict,
        target_document["name"],
    )
    # Attach metadata and headings map to the target document for rendering
    target_document["metadata"] = soup.metadata
    target_document["headings_map"] = soup.headings_map

    # Render the main template with navigation and document content
    return flask.render_template(
        "index.html",
        navigation=navigation_data.hierarchy,
        html=soup.html,
        root_name=ROOT,
        document=target_document,
    )


@app.route("/restore-cleared-cached")
def restore_cleared_cached():
    """
    Route to restore the cleared cache by warming up the cache for all URLs.
    This triggers cache warming in the background for each URL in url_list.txt.
    """
    global cache_warming_in_progress
    global cache_navigation_data

    # Path to the file containing all URLs to warm the cache for
    url_file_path = os.path.join(app.static_folder, "assets", "url_list.txt")

    # Check if the URL list file exists
    if not os.path.exists(url_file_path):
        print("\n\n URL list file not found. \n\n")
        return flask.redirect("/")

    # Read all URLs from the file
    with open(url_file_path, "r") as f:
        urls = [line.strip() for line in f if line.strip()]
    # Build navigation data once and set the cache warming flag
    cache_navigation_data = construct_navigation_data()
    cache_warming_in_progress = True

    # Define a background function to warm the cache and reset flags when done
    def cache_warm_and_unset(urls):
        # Warm the cache for all URLs (runs in a background thread)
        warm_cache_for_urls(urls)
        # After warming, reset global flags and navigation data
        global cache_warming_in_progress
        global cache_navigation_data
        global cache_updated
        cache_updated = True
        cache_warming_in_progress = False
        cache_navigation_data = None

    # Start cache warming in a background thread
    thread = Thread(target=cache_warm_and_unset, args=(urls,))
    thread.start()
    # Print a notification to the console
    print(f"\n\n Started caching for {len(urls)} URLs in the background. \n\n")

    # Redirect the user to the home page
    return flask.redirect("/")


# =========================
# Open Search Routes
# =========================
@app.route("/opensearch/bulk/run", methods=["GET", "POST"])
def opensearch_bulk_run():
    # Require DB
    if "POSTGRESQL_DB_CONNECT_STRING" not in os.environ:
        return ("DB not configured", 503)

    base_url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    tls_ca = os.getenv("OPENSEARCH_TLS_CA")  # single line with \n is OK
    index_name = request.args.get("index") or os.getenv(
        "OPENSEARCH_INDEX", "library-docs"
    )

    if not base_url or not username or not password:
        return ("Missing OPENSEARCH_URL/USERNAME/PASSWORD", 400)

    def fmt_date(d):
        return d.strftime("%d-%m-%Y") if d else None

    def ndjson_iter():
        for doc in db.session.query(Document).yield_per(1000):
            action = {
                "index": {"_index": index_name, "_id": doc.google_drive_id}
            }
            yield json.dumps(action, ensure_ascii=False) + "\n"
            source = {
                "google_drive_ID": doc.google_drive_id,
                "date_planned_review": fmt_date(doc.date_planned_review),
                "type": doc.doc_type,
                "owner": doc.owner,
                "full_html": doc.full_html,
                "path": doc.path,
            }
            if hasattr(doc, "doc_metadata") and doc.doc_metadata is not None:
                source["doc_metadata"] = doc.doc_metadata
            if hasattr(doc, "headings_map") and doc.headings_map is not None:
                source["headings_map"] = doc.headings_map
            yield json.dumps(source, ensure_ascii=False) + "\n"

    # HTTPS client with CA from env
    try:
        http = _requests_session_with_env_ca(tls_ca) if tls_ca else requests
    except Exception as e:
        return jsonify({"error": f"Invalid OPENSEARCH_TLS_CA: {e}"}), 400

    # Send to OpenSearch bulk endpoint
    try:
        resp = http.post(
            f"{base_url.rstrip('/')}/_bulk",
            data=ndjson_iter(),
            headers={"Content-Type": "application/x-ndjson"},
            auth=(username, password),
            timeout=300,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    # Parse response and return a compact summary
    summary = {"status": resp.status_code}
    try:
        body = resp.json()
        summary.update(
            {
                "errors": body.get("errors"),
                "took": body.get("took"),
                "items_count": (
                    len(body.get("items", []))
                    if isinstance(body.get("items"), list)
                    else None
                ),
            }
        )
        if body.get("errors") is True:
            # include first error item for quick debug
            for it in body.get("items", []):
                op = next(iter(it))
                if it[op].get("error"):
                    summary["first_error"] = it[op]["error"]
                    break
    except ValueError:
        summary["text"] = resp.text[:1000]

    return jsonify(summary), resp.status_code


@app.route("/opensearch/indices", methods=["GET"])
def opensearch_list_indices():
    """
    List OpenSearch indices via _cat/indices.
    """
    base_url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    tls_ca = os.getenv("OPENSEARCH_TLS_CA")

    if not (base_url and username and password):
        return jsonify({"error": "OpenSearch not configured"}), 503

    try:
        try:
            http = (
                _requests_session_with_env_ca(tls_ca) if tls_ca else requests
            )
        except NameError:
            http = requests

        resp = http.get(
            f"{base_url.rstrip('/')}/_cat/indices",
            auth=(username, password),
            params={"format": "json", "expand_wildcards": "all"},
            timeout=20,
        )
        # Pass through JSON body and status
        return (
            resp.text,
            resp.status_code,
            {
                "Content-Type": resp.headers.get(
                    "Content-Type", "application/json"
                )
            },
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/opensearch/docs", methods=["GET"])
def opensearch_list_docs():
    """
    List documents from an OpenSearch index.
    Query params:
      - index: index name (default OPENSEARCH_INDEX or 'library-docs')
      - q: optional simple query (uses GET q=... form if provided)
      - size: page size (default 50)
      - from: offset for pagination (default 0)
      - raw=1: return raw OpenSearch response
    """
    base_url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    tls_ca = os.getenv("OPENSEARCH_TLS_CA")

    if not (base_url and username and password):
        return jsonify({"error": "OpenSearch not configured"}), 503

    index_name = request.args.get("index") or os.getenv(
        "OPENSEARCH_INDEX", "library-docs"
    )
    size = int(request.args.get("size", "50"))
    from_ = int(request.args.get("from", "0"))
    q = request.args.get("q")
    raw = request.args.get("raw") == "1"

    try:
        try:
            http = (
                _requests_session_with_env_ca(tls_ca) if tls_ca else requests
            )
        except NameError:
            http = requests

        if q:
            # Simple URI search like docs: GET /{index}/_search?q=...
            includes = "path,owner,type,doc_metadata,full_html"
            resp = http.get(
                f"{base_url.rstrip('/')}/{index_name}/_search",
                auth=(username, password),
                params={
                    "q": q,
                    "size": size,
                    "from": from_,
                    "default_operator": "and",
                    "_source_includes": includes,
                },
                timeout=30,
            )
        else:
            # JSON body search with match_all
            resp = http.post(
                f"{base_url.rstrip('/')}/{index_name}/_search",
                auth=(username, password),
                headers={"Content-Type": "application/json"},
                json={
                    "query": {"match_all": {}},
                    "_source": {
                        "includes": [
                            "path",
                            "owner",
                            "type",
                            "doc_metadata",
                            "full_html",
                        ]
                    },
                    "size": size,
                    "from": from_,
                },
                timeout=30,
            )

        data = resp.json()
        if raw:
            return jsonify(data), resp.status_code

        hits = data.get("hits", {})
        total = (
            hits.get("total", {}).get("value")
            if isinstance(hits.get("total"), dict)
            else hits.get("total")
        )
        items = []
        for h in hits.get("hits", []):
            src = h.get("_source") or {}
            meta = src.get("doc_metadata") or {}
            items.append(
                {
                    "id": h.get("_id"),
                    "score": h.get("_score"),
                    "path": src.get("path"),
                    "owner": src.get("owner"),
                    "type": src.get("type"),
                    "title": meta.get("title"),
                    "full_html_snippet": (src.get("full_html") or "")[:200],
                }
            )

        return (
            jsonify(
                {
                    "index": index_name,
                    "from": from_,
                    "size": size,
                    "total": total,
                    "hits": items,
                }
            ),
            resp.status_code,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# =========================
# App Lifecycle Hooks
# =========================
@app.before_request
def initialized():
    """
    Before request hook to initialize the Google Drive instance
    and the navigation builder.
    This is executed only once per application context.
    """
    global initialized_executed, gdrive_instance, nav_changes
    if not initialized_executed:
        initialized_executed = True
        with app.app_context():
            gdrive_instance = get_google_drive_instance()
            nav_changes = NavigationBuilder(gdrive_instance, ROOT)
            get_list_of_urls()
            init_scheduler(app)


# =========================
# Main Entrypoint
# =========================
if __name__ == "__main__":
    app.run()
