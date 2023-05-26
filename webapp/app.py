import os
import flask
import talisker

from canonicalwebteam.flask_base.app import FlaskBase

from webapp.googledrive import Drive
from webapp.parser import Parser
from webapp.navigation import Navigation
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

drive = None


def init_drive():
    global drive
    if drive is None:
        drive = Drive()
    return drive


@app.route("/")
@app.route("/<path:path>")
def document(path=None):
    navigation = Navigation(init_drive())

    try:
        document = target_document(path, navigation.hierarchy)
    except Exception as e:
        err = "Error, document does not exist."
        print(f"{err}\n {e}")
        flask.abort(404, description=err)

    soup = Parser(
        init_drive(), document["id"], navigation.object_dict, document["name"]
    )

    return flask.render_template(
        "index.html",
        navigation=navigation.hierarchy,
        html=soup.html,
        root_name=ROOT,
        document_id=document["id"],
        path=path,
    )


def target_document(path, navigation):
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
