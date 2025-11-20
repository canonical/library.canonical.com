import os
import ssl
import base64
import binascii
import textwrap
import requests


def requests_session_with_env_ca(raw):
    """Build a requests.Session pinned to a CA provided via env.

    Accepts OPENSEARCH_TLS_CA as:
      - Inline PEM chain with literal '\n'
      - Regular PEM (multi-line)
      - Base64 of PEM/DER
    Returns a requests.Session with an SSLContext configured with this CA,
    or None if raw is falsy (caller can fall back to requests).
    """
    if not raw:
        return None

    val = str(raw).strip().strip('"').strip("'")
    if "\n" in val:
        val = val.replace("\\n", "\n")
    val = val.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.lstrip() for ln in val.splitlines()]
    val = "\n".join(lines).strip()

    cadata = None  # str or bytes
    if "BEGIN CERTIFICATE" in val:
        pem = textwrap.dedent(val).strip()
        if not pem.endswith("\n"):
            pem += "\n"
        cadata = pem
    else:
        try:
            raw_bytes = base64.b64decode(val, validate=True)
        except binascii.Error:
            raise ValueError("OPENSEARCH_TLS_CA is neither PEM nor base64")
        try:
            txt = raw_bytes.decode("utf-8")
            cadata = txt if "BEGIN CERTIFICATE" in txt else raw_bytes
        except UnicodeDecodeError:
            cadata = raw_bytes

    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cadata=cadata)

    from requests.adapters import HTTPAdapter

    class SSLContextAdapter(HTTPAdapter):
        def __init__(self, ssl_context=None, **kwargs):
            self.ssl_context = ssl_context
            super().__init__(**kwargs)

        def init_poolmanager(self, *args, **kwargs):
            kwargs["ssl_context"] = self.ssl_context
            return super().init_poolmanager(*args, **kwargs)

        def proxy_manager_for(self, *args, **kwargs):
            kwargs["ssl_context"] = self.ssl_context
            return super().proxy_manager_for(*args, **kwargs)

    s = requests.Session()
    s.mount("https://", SSLContextAdapter(ctx))
    return s


def ensure_highlight_limit(index_name: str, limit: int = 5_000_000) -> None:
    """Ensure OpenSearch index setting index.highlight.max_analyzed_offset.

    No-ops if OPENSEARCH_URL/USERNAME/PASSWORD aren't set.
    """
    base_url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    tls_ca = os.getenv("OPENSEARCH_TLS_CA")
    if not (base_url and username and password):
        return
    http = requests_session_with_env_ca(tls_ca) if tls_ca else requests
    try:
        http.put(
            f"{base_url.rstrip('/')}/{index_name}/_settings",
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            json={"index.highlight.max_analyzed_offset": limit},
            timeout=20,
        )
    except Exception as e:
        print(f"[search] failed to set max_analyzed_offset: {e}", flush=True)
