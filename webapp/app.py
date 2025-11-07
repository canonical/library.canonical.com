# =========================
# Imports and Environment
# =========================
import os
import copy
import flask
import dotenv
import json
import requests
from threading import Thread
from flask import request, g, session

# import talisker
from canonicalwebteam.flask_base.app import FlaskBase

from webapp.services.document_service import get_or_parse_document
from webapp.navigation_builder import NavigationBuilder
from webapp.sso import init_sso
from webapp.db import db
from webapp.extensions import cache, init_cache
import webapp.state as state
from webapp.utils.make_snippet import render_snippet
from webapp.services.drive_service import get_google_drive_instance
from webapp.services.navigation_service import (
    reset_navigation_flags,
    construct_navigation_data,
    get_navigation_data,
    get_target_document,
)
from webapp.services.cache_warm import (
    warm_cache_for_urls,
)
from webapp.services.opensearch_service import (
    requests_session_with_env_ca,
    ensure_highlight_limit,
)
from webapp.scheduler import init_scheduler, scheduled_get_changes
from webapp.opensearch_routes import opensearch_bp
from webapp.models import Document
from webapp.services.url_redirects import (
    get_list_of_urls,
    find_broken_url,
)
from webapp.services.db_bootstrap import (
    ensure_documents_table,
    ensure_documents_columns,
)

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

app.register_blueprint(opensearch_bp)


if "POSTGRESQL_DB_CONNECT_STRING" in os.environ:
    print("\n\nUsing PostgreSQL database\n\n", flush=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "POSTGRESQL_DB_CONNECT_STRING"
    )
    db.init_app(app)
    ensure_documents_table(app)
    ensure_documents_columns(app)
    # Only for Local testing
    # with app.app_context():
    #     db.create_all()

# Initialize the cache extension (Redis or Simple)
init_cache(app)


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
    # Ensure nothing is highlighted/expanded on the Search page
    reset_navigation_flags(navigation_data.hierarchy)

    base_url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    tls_ca = os.getenv("OPENSEARCH_TLS_CA")

    search_results = None
    used_opensearch = False

    if base_url and username and password:
        try:
            http = requests_session_with_env_ca(tls_ca) if tls_ca else requests
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
                    ensure_highlight_limit(index_name, 5_000_000)
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
        # Provide an empty previous_slug so the client-side nav
        # doesn't try to select a current page in the tree.
        previous_slug="",
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
@cache.cached(timeout=604800)
def document(path=None):
    """
    The entire site is rendered by this function (except /search). As all
    pages use the same template, the only difference between them is the
    content.
    """

    # Handle navigation data refresh after cache warming or URL update
    if state.cache_updated:
        state.cache_updated = False
        navigation_data = construct_navigation_data()
        g.navigation_data = navigation_data
    # Handle navigation data refresh after URL update
    elif state.url_updated and not state.cache_warming_in_progress:
        state.url_updated = False
        navigation_data = construct_navigation_data()
        g.navigation_data = navigation_data
    # If cache warming is in progress, use a copy of the navigation data
    elif state.cache_warming_in_progress:
        print("Cache warming in progress, skipping navigation construction.")
        navigation_data = copy.deepcopy(state.cache_navigation_data)
    # Otherwise, get navigation data from cache or build if needed
    else:
        navigation_data = get_navigation_data()
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
    # use state flags

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
    state.cache_navigation_data = construct_navigation_data()
    state.cache_warming_in_progress = True

    # Define a background function to warm the cache and reset flags when done
    def cache_warm_and_unset(urls):
        # Warm the cache for all URLs (runs in a background thread)
        warm_cache_for_urls(urls, app, construct_navigation_data, document)
        # After warming, reset global flags and navigation data
        state.cache_updated = True
        state.cache_warming_in_progress = False
        state.cache_navigation_data = None

    # Start cache warming in a background thread
    thread = Thread(target=cache_warm_and_unset, args=(urls,))
    thread.start()
    # Print a notification to the console
    print(f"\n\n Started caching {len(urls)} URLs in the background. \n\n")

    # Redirect the user to the home page
    return flask.redirect("/")


@app.route("/clear-all-views")
def clear_all_views():
    """
    Clear cached HTML for all known document routes using url_list.txt.
    Also clears the root view and navigation cache. Useful when a stale
    hashed CSS was baked into cached pages and needs to be purged.
    """
    # Clear root and navigation first
    cache.delete("view//")
    cache.delete("navigation")

    url_file_path = os.path.join(app.static_folder, "assets", "url_list.txt")
    if not os.path.exists(url_file_path):
        print(
            "[cache] url_list.txt not found cleared root/nav only", flush=True
        )
        return flask.redirect("/")

    removed = 0
    with open(url_file_path, "r") as f:
        for line in f:
            url = line.strip()
            if not url:
                continue
            path = url.lstrip("/")
            key = f"view//{path}"
            if cache.delete(key):
                removed += 1

    print(f"[cache] cleared {removed} view entries from url_list", flush=True)
    return flask.redirect("/")


# =========================
# OpenSearch routes moved to webapp/opensearch_routes.py
# =========================


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
    if not state.initialized_executed:
        state.initialized_executed = True
        with app.app_context():
            state.gdrive_instance = get_google_drive_instance()
            state.nav_changes = NavigationBuilder(state.gdrive_instance, ROOT)
            get_list_of_urls()
            init_scheduler(app, document)


# =========================
# Main Entrypoint
# =========================
if __name__ == "__main__":
    app.run()
