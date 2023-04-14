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
        document = navigation.hierarchy["home"]
    else:
        try:
            document = target_document(path, navigation.hierarchy)
        except Exception as e:
            err = "Error, document does not exist."
            print(f"{err}\n {e}")
            flask.abort(404, description=err)

    soup = Parser(drive, document["id"])

    return flask.render_template(
        "index.html", navigation=navigation.hierarchy, html=soup.html
    )


def target_document(path, navigation):
    split_slug = path.split("/")
    target_page = navigation
    for index, slug in enumerate(split_slug):
        if len(split_slug) == index + 1:
            target_page[slug]["active"] = True
            return target_page[slug]
        target_page[slug]["expanded"] = True
        target_page = target_page[slug]["children"]
