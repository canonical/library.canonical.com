import flask
import talisker

from canonicalwebteam.flask_base.app import FlaskBase

from webapp.googledrive import Drive
from webapp.parser import Parser
from webapp.navigation import Navigation

drive = Drive()

app = FlaskBase(
    __name__,
    "canonical.reference-library.com",
    template_folder="../templates",
    template_404="404.html",
    template_500="500.html",
    static_folder="../static",
)

session = talisker.requests.get_session()

@app.route("/")
@app.route("/<path:path>")
def document(path=None):
    navigation = Navigation(drive)

    if not path:
        document_id = navigation.hierarchy["home"]["id"]
    else:
        try:
            document_id = get_page_id(path, navigation.hierarchy)
        except Exception as e:
            err = "Error, document does not exist."
            print(f"{err}\n {e}")
            flask.abort(404, description=err)

    soup = Parser(drive, document_id)

    return flask.render_template(
        "index.html", navigation=navigation.hierarchy, document=soup.html
    )


def get_page_id(path, navigation):
    split_slug = path.split("/")
    target_page = navigation
    for index, slug in enumerate(split_slug):
        if len(split_slug) == index + 1:
            return target_page[slug]["id"]
        target_page = target_page[slug]["children"]
