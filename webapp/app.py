import os
import flask
import redis
from apscheduler.schedulers.background import BackgroundScheduler

# import talisker
from flask import request, g, session
from canonicalwebteam.flask_base.app import FlaskBase

from webapp.googledrive import GoogleDrive
from webapp.parser import Parser
from webapp.navigation_builder import NavigationBuilder
from webapp.sso import init_sso
from webapp.spreadsheet import GoggleSheet
from flask_caching import Cache


# Initialize Flask app
ROOT = os.getenv("ROOT_FOLDER", "library")
TARGET_DRIVE = os.getenv("TARGET_DRIVE", "0ABG0Z5eOlOvhUk9PVA")
URL_DOC = os.getenv("URL_FILE", "16mTPcMn9hxjgra62ArjL6sTg75iKiqsdN99vtmrlyLg")


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

# Initialize caching
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
    global gdrive_instance
    google_drive = gdrive_instance
    changes = google_drive.get_latest_changes()
    nav_changes = process_changes(changes, nav_changes, gdrive_instance)


def process_changes(changes, navigation_data, google_drive):
    global url_updated
    """
    Process the changes
    """
    new_nav = NavigationBuilder(google_drive, ROOT)
    print(navigation_data)
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
                        print("NAME or LOCATION CHANGE")
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


@app.route("/")
@app.route("/<path:path>")
@cache.cached(timeout=5)  # 7 days cached = 604800 seconds 1 day = 86400
def document(path=None):
    global url_updated
    global global_scheduler_starter
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

    if path is not None and "clear-cache" in path:
        cache.clear()
        new_path = path.replace("clear-cache", "")
        return flask.redirect("/" + new_path)
    else:
        try:
            target_document = get_target_document(
                path, navigation_data.hierarchy
            )
        except KeyError:
            new_path = find_broken_url(path)
            if new_path:
                path = new_path
                return flask.redirect("/" + path)
            else:
                err = "Error, document does not exist."
                flask.abort(404, description=err)

        soup = Parser(
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
    print("Initializing the scheduler...")  # Debugging log

    def scheduled_task():
        global nav_changes
        global gdrive_instance
        print("Executing scheduled task...")  # Debugging log
        with app.app_context():
            print("Context acquired.")  # Debugging log
            google_drive = gdrive_instance
            print(nav_changes)
            navigation = nav_changes
            changes = google_drive.get_latest_changes()
            new_nav = process_changes(changes, navigation, google_drive)
            nav_changes = new_nav
            print("Scheduled task completed successfully.")  # Debugging log

    # Initialize the scheduler
    scheduler = BackgroundScheduler()
    print("Scheduler initialized.")  # Debugging log
    scheduler.add_job(scheduled_task)  # Run once
    scheduler.add_job(
        scheduled_task, "interval", minutes=2
    )  # Run every 5 minutes
    scheduler.start()
    print("Scheduler started.")  # Debugging log
    return scheduler


nav_changes = None
url_updated = False
gdrive_instance = None

if __name__ == "__main__":
    with app.app_context():
        print("CONTEXTTTTTT\n\n\n\n HELP")
        gdrive_instance = get_google_drive_instance()
        nav_changes = NavigationBuilder(gdrive_instance, ROOT)
    init_scheduler(app)
    app.run()
