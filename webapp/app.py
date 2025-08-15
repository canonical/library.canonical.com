# =========================
# Imports and Environment
# =========================
import os
import copy
import flask
import redis
from apscheduler.schedulers.background import BackgroundScheduler
import dotenv

# import talisker
from flask import request, g, session, has_request_context
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
if "POSTGRESQL_DB_CONNECT_STRING" in os.environ:
    print("\n\nUsing PostgreSQL database\n\n", flush=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "POSTGRESQL_DB_CONNECT_STRING"
    )
    db.init_app(app)
    from webapp.models import Document  # noqa: F401 needed for db.create_all()

    with app.app_context():
        db.create_all()

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
    """
    Warm up the cache for a list of URLs by using a thread pool to
    handle multiple URLs concurrently.
    """
    with app.app_context():
        navigation_data = construct_navigation_data()
        with ThreadPoolExecutor(
            max_workers=8
        ) as executor:  # Adjust workers as needed
            executor.map(
                lambda url: warm_single_url(url, navigation_data), urls
            )
        print(f"\n\n Finished cache warming for {len(urls)} URLs. \n\n")


def get_cache_ttl(key):
    """
    Returns the TTL (seconds until expiry) for a cache key if Redis is used.
    If SimpleCache is used, returns None.
    """
    # Check if Redis is being used as the cache backend
    if isinstance(cache.cache, redis.client.Redis):
        redis_key = key
        ttl = cache.cache.ttl(redis_key)
        return ttl
    else:
        print("TTL is not supported for SimpleCache.")
        return None


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
        redis_client = cache.cache._read_client
        for url in urls:
            # The cache key must match your Flask-Caching key pattern
            cache_key = f"view//{url.lstrip('/')}"
            ttl = redis_client.ttl(cache_key)
            if ttl < 3600:  # Less than 1 hour
                expiring_urls.append({"url": url, "ttl": ttl})
    else:
        print("TTL checking is only supported with Redis cache.")

    return expiring_urls


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
        global cache_navigation_data
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

    # Initialize the scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_task)  # Run once
    scheduler.add_job(check_status_cache)  # Run on load
    scheduler.add_job(
        scheduled_task, "interval", minutes=5
    )  # Run every 5 minutes
    scheduler.add_job(
        check_status_cache,
        "cron",
        day_of_week="sun",
        hour=7,
        minute=0,
        id="weekly_cache_check",
    )  # Run every Sunday at 7:00 AM
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
    Route to search the Google Drive. The search results are displayed in a
    separate page.
    """
    query = request.args.get("q", "")
    google_drive = get_google_drive_instance()
    search_results = google_drive.search_drive(query)
    navigation_data = get_navigation_data()

    return flask.render_template(
        "search.html",
        search_results=search_results,
        doc_reference_dict=navigation_data.doc_reference_dict,
        query=query,
        TARGET_DRIVE=TARGET_DRIVE,
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
    Clear cache for a specific document
    """
    print("Clearing cache")
    print("PATH\n", path)
    if path is None:
        new_path = ""
    else:
        new_path = path.replace("/clear-cache", "")
    cache_key = "view//%s" % new_path

    print("Cache Key", cache_key)
    if cache.delete(cache_key):  # Delete the cache entry
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
    global cache_warming_in_progress
    global cache_navigation_data
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
        print(
            "Cache warming in progress, skipping navigation construction."
        )
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
    print(
        f"\n\n Started caching for {len(urls)} URLs in the background. \n\n"
    )

    # Redirect the user to the home page
    return flask.redirect("/")


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
