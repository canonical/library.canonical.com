import os
import flask
import talisker

from canonicalwebteam.flask_base.app import FlaskBase

from webapp.googledrive import GoogleDrive
from webapp.parser import Parser
from webapp.navigation_builder import NavigationBuilder
from webapp.sso import init_sso

ROOT = os.getenv("ROOT_FOLDER", "library")

app = FlaskBase(
    __name__,
    "library.canonical.com",
    template_folder="../templates",
    template_404="404.html",
    template_500="500.html",
    static_folder="../static",
)

session = talisker.requests.get_session()
init_sso(app)


@app.route("/")
@app.route("/<path:path>")
def document(path=None):
    """
    The entire site is rendered by this function. As all pages use the same
    template, the only difference between them is the content.
    """
    navigation = NavigationBuilder(get_google_drive_instance(), ROOT)

    try:
        target_document = get_target_document(path, navigation.hierarchy)
    except KeyError as e:
        err = "Error, document does not exist."
        flask.abort(404, description=err)

    soup = Parser(
        get_google_drive_instance(),
        target_document["id"],
        navigation.doc_reference_dict,
        target_document["name"],
    )

    target_document["metadata"] = soup.metadata
    target_document["headings_map"] = soup.headings_map

    return flask.render_template(
        "index.html",
        navigation=navigation.hierarchy,
        html=soup.html,
        root_name=ROOT,
        document=target_document,
    )


def get_google_drive_instance():
    """
    Return a singleton instance of GoogleDrive
    """
    if not hasattr(get_google_drive_instance, "_instance"):
        get_google_drive_instance._instance = GoogleDrive()
    return get_google_drive_instance._instance


def get_target_document(path, navigation):
    """
    Given a URL path, find the related document in the navigation hierarchy,
    update the status of that document, and return it.
    """
    if not path:
        navigation["index"]["active"] = True
        return navigation["index"]

    split_slug = path.split("/")
    target_page = navigation

    for index, slug in enumerate(split_slug):
        if slug not in target_page:
            raise KeyError(f"Slug '{slug}' not found in navigation.")

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


if __name__ == "__main__":
    app.run()
