import flask
import talisker

from canonicalwebteam.flask_base.app import FlaskBase

from webapp.googledrive import Drive
from webapp.parser import Parser

drive = Drive()

app = FlaskBase(
    __name__,
    "canonical.reference-library.com",
    template_folder="../templates",
    static_folder="../static",
)

session = talisker.requests.get_session()


@app.route("/")
def index():
    items = drive.get_first_10_documents()

    return flask.render_template("index.html", items=items)


@app.route("/document/<document_id>")
def document(document_id):
    soup = Parser(drive, document_id)

    return flask.render_template("document.html", document=soup.html)
