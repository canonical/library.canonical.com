import os
import flask
import redis
from apscheduler.schedulers.background import BackgroundScheduler
import dotenv

# import talisker
from flask import request, g, session
from canonicalwebteam.flask_base.app import FlaskBase

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
        print(f"Setting environment variable {key} to {key[6:]}", flush=True)
        os.environ[key[6:]] = value

dotenv.load_dotenv(".env")
dotenv.load_dotenv(".env.local", override=True)

# Initialize Flask app
ROOT = os.getenv("ROOT_FOLDER", "library")
TARGET_DRIVE = os.getenv("TARGET_DRIVE", "0ABG0Z5eOlOvhUk9PVA")
URL_DOC = os.getenv("URL_FILE", "16mTPcMn9hxjgra62ArjL6sTg75iKiqsdN99vtmrlyLg")
DRAFTS_URL = (
    "https://drive.google.com/drive/folders/1cI2ClDWDzv3osp0Adn0w3Y7zJJ5h08ua"
)


app = FlaskBase(
    __name__,
    "library.canonical.com",
    template_folder="../templates",
    template_404="404.html",
    template_500="500.html",
    static_folder="../static",
)

# Initialize session and single Drive instance
# TODO: Implement Talisker
# It is used to manage error logging
# session = talisker.requests.get_session()
init_sso(app)

if "POSTGRES_DB_HOST" in os.environ:
    print("\n\nUsing PostgreSQL database\n\n")
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://%s:%s@%s:%s/%s" % (
        os.getenv("POSTGRES_DB_USER", "postgres"),
        os.getenv("POSTGRES_DB_PASSWORD", "password"),
        os.getenv("POSTGRES_DB_HOST", "localhost"),
        os.getenv("POSTGRES_DB_PORT", 5432),
        os.getenv("POSTGRES_DB_NAME", "library"),
    )
    db.init_app(app)
    from webapp.models import Document  # noqa: F401 needed for db.create_all()

    with app.app_context():
        db.create_all()

# Initialize caching
if "CACHE_REDIS_HOST" in os.environ:
    print("\n\nUsing Redis cache\n\n")
    cache = Cache(
        app,
        config={
            "CACHE_TYPE": "RedisCache",
            "CACHE_REDIS_HOST": os.getenv(
                "REDIS_DB_HOST", "localhost"
            ),  # or your Redis server address
            "CACHE_REDIS_PORT": os.getenv(
                "REDIS_DB_PORT", 6379
            ),  # default Redis port
            "CACHE_REDIS_DB": os.getenv(
                "REDIS_DB_NAME", 0
            ),  # default Redis DB # optional, overrides host/port/db
        },
    )
else:
    cache = Cache(app, config={"CACHE_TYPE": "simple"})

cache.init_app(app)


# Initialize Redis
redis = redis.Redis(host="localhost", port=6379, db=0)


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
    for u in g.list_of_urls:
        if u["old"] == url:
            return u["new"]
    return None


def scheduled_get_changes():
    global nav_changes
    google_drive = gdrive_instance
    changes = google_drive.get_latest_changes()
    nav_changes = process_changes(changes, nav_changes, gdrive_instance)


def process_changes(changes, navigation_data, google_drive):
    global url_updated
    """
    Process the changes
    """
    new_nav = NavigationBuilder(google_drive, ROOT)
    print("Processing Changes")
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
    Construct the navigation data and cache it.
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


@app.route("/refresh-navigation")
def refresh_navigation():
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


@app.route("/update-urls")
def update_urls(path=None):
    """
    Route to search the Google Drive. The search results are displayed in a
    separate page.
    """
    scheduled_get_changes()
    new_path = path.replace("update-urls", "")
    return flask.redirect("/" + new_path)


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
    Route to create a copy of the template document.
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
    """
    The entire site is rendered by this function (except /search). As all
    pages use the same template, the only difference between them is the
    content.
    """
    get_list_of_urls()
    if url_updated:
        url_updated = False
        navigation_data = construct_navigation_data()
        g.navigation_data = navigation_data
    else:
        navigation_data = get_navigation_data()

    try:
        target_document = get_target_document(path, navigation_data.hierarchy)
    except KeyError:
        new_path = find_broken_url(path)
        if new_path:
            path = new_path
            return flask.redirect("/" + path)
        else:
            err = "Error, document does not exist."
            flask.abort(404, description=err)

    soup = get_or_parse_document(
        get_google_drive_instance(),
        target_document["id"],
        navigation_data.doc_reference_dict,
        target_document["name"],
    )

    target_document["metadata"] = soup.metadata
    target_document["headings_map"] = soup.headings_map

    return flask.render_template(
        "index.html",
        navigation=navigation_data.hierarchy,
        html=soup.html,
        root_name=ROOT,
        document=target_document,
    )


def init_scheduler(app):

    def scheduled_task():
        global nav_changes
        with app.app_context():
            google_drive = gdrive_instance
            navigation = nav_changes
            changes = google_drive.get_latest_changes()
            new_nav = process_changes(changes, navigation, google_drive)
            nav_changes = new_nav

    # Initialize the scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_task)  # Run once
    scheduler.add_job(
        scheduled_task, "interval", minutes=5
    )  # Run every 5 minutes
    scheduler.start()
    return scheduler


nav_changes = None
url_updated = False
gdrive_instance = None

initialized_executed = False


@app.before_request
def initialized():
    global initialized_executed, gdrive_instance, nav_changes
    if not initialized_executed:
        initialized_executed = True
        with app.app_context():
            gdrive_instance = get_google_drive_instance()
            nav_changes = NavigationBuilder(gdrive_instance, ROOT)
            init_scheduler(app)


if __name__ == "__main__":
    app.run()
