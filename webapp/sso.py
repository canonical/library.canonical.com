import os
from urllib.parse import quote_plus, urlencode
import flask
import socket
from authlib.integrations.flask_client import OAuth

# OIDC Configuration
OIDC_ISSUER = os.getenv("OIDC_ISSUER", "https://login.ubuntu.com")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET")
OIDC_SCOPES = os.getenv("OIDC_SCOPES", "openid profile email").split()
REQUIRED_TEAM = os.getenv("OPENID_LAUNCHPAD_TEAM", "canonical")

for key, value in os.environ.items():
    if key.startswith("FLASK_"):
        # Set environment variable without the 'FLASK_' prefix
        os.environ[key[6:]] = value

# Global OAuth instance
oauth = OAuth()


def check_team_membership(user_info):
    """
    Check if user is a member of the required team.
    This depends on the OIDC provider's implementation.
    For login.ubuntu.com, teams might be in 'groups' or a custom claim.
    """
    # Check if teams/groups are in the user info
    teams = user_info.get('teams', [])
    groups = user_info.get('groups', [])
    
    # Combine teams and groups
    all_memberships = teams + groups
    
    # Check if required team is in the memberships
    if REQUIRED_TEAM:
        # Support both team name and team slug formats
        for membership in all_memberships:
            if isinstance(membership, str):
                if REQUIRED_TEAM in membership or membership in REQUIRED_TEAM:
                    return True
            elif isinstance(membership, dict):
                if membership.get('name') == REQUIRED_TEAM or membership.get('slug') == REQUIRED_TEAM:
                    return True
        return False
    
    # If no required team specified, allow access
    return True


def init_sso(app):
    """Initialize OIDC authentication with Authlib"""
    
    # Initialize OAuth with app
    oauth.init_app(app)
    
    # Register the OIDC provider
    oauth.register(
        name='oidc',
        client_id=OIDC_CLIENT_ID,
        client_secret=OIDC_CLIENT_SECRET,
        server_metadata_url=f'{OIDC_ISSUER}/.well-known/openid-configuration',
        client_kwargs={
            'scope': ' '.join(OIDC_SCOPES),
        }
    )

    @app.route("/login")
    def login():
        """Initiate OIDC login flow"""
        print("Login handler called", flush=True)
        
        # If already logged in, redirect to next URL
        if "user" in flask.session or "openid" in flask.session:
            return flask.redirect(flask.request.args.get("next", "/"))
        
        # Build the callback URL
        redirect_uri = flask.url_for("authorize", _external=True)
        
        # Store the 'next' parameter in session for after login
        next_url = flask.request.args.get("next", "/")
        flask.session["next_url"] = next_url
        
        # Redirect to OIDC provider for authentication
        return oauth.oidc.authorize_redirect(redirect_uri)

    @app.route("/authorize")
    def authorize():
        """OIDC callback handler"""
        try:
            # Exchange authorization code for tokens
            token = oauth.oidc.authorize_access_token()
            
            # Get user info from the ID token or userinfo endpoint
            user_info = token.get('userinfo')
            if not user_info:
                # If userinfo not in token, fetch it
                user_info = oauth.oidc.userinfo()
            
            print(f"User info received: {user_info.get('email')}", flush=True)
            
            # Check team membership
            if not check_team_membership(user_info):
                print(f"User {user_info.get('email')} not in required team: {REQUIRED_TEAM}", flush=True)
                flask.abort(403, description=f"Access denied. You must be a member of the '{REQUIRED_TEAM}' team.")
            
            # Store user information in session
            flask.session["user"] = {
                "email": user_info.get("email"),
                "name": user_info.get("name") or user_info.get("preferred_username"),
                "sub": user_info.get("sub"),
                "teams": user_info.get("teams", []),
                "groups": user_info.get("groups", []),
            }
            
            # For backward compatibility, also store as "openid"
            flask.session["openid"] = {
                "email": user_info.get("email"),
                "fullname": user_info.get("name") or user_info.get("preferred_username"),
                "identity_url": user_info.get("sub"),
            }
            
            print(f"User logged in: {user_info.get('email')}", flush=True)
            
            # Redirect to the originally requested page
            next_url = flask.session.pop("next_url", "/")
            return flask.redirect(next_url)
            
        except Exception as e:
            print(f"Authorization error: {e}", flush=True)
            flask.abort(401, description="Authentication failed. Please try again.")

    @app.route("/logout")
    def logout():
        """Logout and clear session"""
        # Clear the session
        flask.session.clear()
        
        # Optionally redirect to OIDC provider's logout endpoint
        # This depends on whether your OIDC provider supports RP-initiated logout
        logout_url = os.getenv("OIDC_LOGOUT_URL")
        if logout_url:
            # Build the post-logout redirect URI
            post_logout_redirect_uri = flask.url_for("document", path=None, _external=True)
            return flask.redirect(
                f"{logout_url}?{urlencode({'post_logout_redirect_uri': post_logout_redirect_uri})}"
            )
        
        return flask.redirect("/")

    @app.before_request
    def before_request():
        """Ensure user is authenticated for protected routes"""
        # Public routes that don't require authentication
        public_routes = ["/login", "/authorize", "/logout"]
        
        # Skip authentication for public routes
        if flask.request.path in public_routes:
            return
        
        # Skip authentication for static files and status endpoints
        if flask.request.path.startswith("/_status") or flask.request.path.startswith("/static"):
            return
        
        # Check if user is authenticated
        if "user" not in flask.session and "openid" not in flask.session:
            # Save the current URL to redirect back after login
            return flask.redirect(
                "/login?next=" + quote_plus(flask.request.path)
            )

    @app.after_request
    def add_headers(response):
        """
        Generic rules for headers to add to all requests
        - X-Hostname: Mention the name of the host/pod running the application
        - Cache-Control: Add cache-control headers for public and private pages
        """
        response.headers["X-Hostname"] = socket.gethostname()

        if response.status_code == 200:
            if flask.session:
                response.headers["Cache-Control"] = "private"

        return response

