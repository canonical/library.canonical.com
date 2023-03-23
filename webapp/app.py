import flask
import talisker

# Packages
from canonicalwebteam.flask_base.app import FlaskBase

# Rename your project below
app = FlaskBase(
    __name__,
    "canonical.reference-library.com",
    template_folder="../templates",
    static_folder="../static",
)

session = talisker.requests.get_session()


@app.route("/")
def index():
    return flask.render_template("index.html")
