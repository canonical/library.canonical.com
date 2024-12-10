import os
import flask
import talisker
from flask import request, g
from canonicalwebteam.flask_base.app import FlaskBase

from webapp.googledrive import GoogleDrive
from webapp.parser import Parser
from webapp.navigation_builder import NavigationBuilder
from webapp.sso import init_sso

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
session = talisker.requests.get_session()
init_sso(app)


def get_google_drive_instance():
    """
    Return a singleton instance of GoogleDrive and cache in Flask's 'g'
    object.
    """
    if "google_drive" not in g:
        g.google_drive = GoogleDrive()
    return g.google_drive


def get_list_of_urls():
    """
    Return a list of urls from Google Drive and cache in Flask's 'g'
    object.
    """
    if "list_of_urls" not in g:
        google_drive = get_google_drive_instance()
        urls = []
        list = google_drive.fetch_spreadsheet(URL_DOC)
        lines = list.split('\n')[1:]
        for line in lines:
            url = line.split(',')
            urls.append({'old': url[0], 'new': url[1].replace('\r', '')})
        g.list_of_urls = urls


def find_broken_url(url):
    """
    Find the new url for a given old url
    """
    for u in g.list_of_urls:
        if u['old'] == url:
            return u['new']
    return None


def get_navigation_data():
    """
    Return the navigation data from Google Drive and cache in Flask's 'g'
    object.
    """
    if "navigation_data" not in g:
        google_drive = get_google_drive_instance()
        g.navigation_data = NavigationBuilder(google_drive, ROOT)
    return g.navigation_data


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


@app.route("/")
@app.route("/<path:path>")
def document(path=None):
    """
    The entire site is rendered by this function (except /search). As all
    pages use the same template, the only difference between them is the
    content.
    """
    get_list_of_urls()
    navigation_data = get_navigation_data()

    try:
        target_document = get_target_document(path, navigation_data.hierarchy)
    except KeyError:
        new_path = find_broken_url(path)
        if new_path:
            path = new_path
            return flask.redirect("/"+path)
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


if __name__ == "__main__":
    app.run()
