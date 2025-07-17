import os

for key, value in os.environ.items():
    if key.startswith("FLASK_"):
        # Set environment variable without the 'FLASK_' prefix
        os.environ[key[6:]] = value


def sanitize_env(env_var):
    """Remove escape slashes and string environment variables"""
    if env_var is not None:
        return env_var.replace("\\n", "\n").replace('"', "")


PROJECT_ID = sanitize_env(os.getenv("PROJECT_ID"))
PRIVATE_KEY_ID = sanitize_env(os.getenv("PRIVATE_KEY_ID"))
PRIVATE_KEY = sanitize_env(os.getenv("PRIVATE_KEY"))
CLIENT_EMAIL = sanitize_env(os.getenv("CLIENT_EMAIL"))
CLIENT_ID = sanitize_env(os.getenv("CLIENT_ID"))
CLIENT__X509_CERT_URL = sanitize_env(os.getenv("CLIENT__X509_CERT_URL"))

SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": PROJECT_ID,
    "private_key_id": PRIVATE_KEY_ID,
    "private_key": PRIVATE_KEY,
    "client_email": CLIENT_EMAIL,
    "client_id": CLIENT_ID,
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": CLIENT__X509_CERT_URL,
}
